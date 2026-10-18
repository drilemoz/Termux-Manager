package com.termux.app;

import android.content.Context;

import com.termux.shared.logger.Logger;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Offline installation of a bundled copy of TermuxManager after the stock Termux
 * bootstrap has been extracted. This is not a replacement for the bootstrap.
 *
 * Installs or restores missing managed files; never overwrites user's content.
 * All extracted files are verified against an independent embedded SHA-256 index.
 */
final class TermuxManagerBundle {
    private static final String TAG = "TermuxManagerBundle";
    private static final String ZIP_ASSET = "termux-manager.bundle.zip";
    private static final String INDEX_ASSET = "termux-manager.bundle-index.tsv";
    private static final String INSTALLED_MARKER = ".termux-manager-bundle-installed";
    private static final String VERSION_INDEX_MARKER = ".termux-manager-file-index.tsv";
    private static final String LEGACY_INDEX_ASSET = "termux-manager.legacy-index-1.0.126.tsv";
    private static final String TERMINAL_PALETTE =
        "background=#012456\nforeground=#CCCCCC\ncursor=#FFFFFF\n";
    private static final String AUTOSTART_MARKER = "# TERMUX_MANAGER_BUNDLE_AUTOSTART_V1";
    private static final long MAX_UNCOMPRESSED_BYTES = 64L * 1024L * 1024L;
    private static final int MAX_ENTRIES = 1500;

    private TermuxManagerBundle() {}

    static void install(Context context) {
        try {
            installChecked(context);
        } catch (IOException | RuntimeException e) {
            // Preserve the stock Termux terminal even if the optional bundled
            // Manager fails. A failed Manager install must not wipe $PREFIX.
            Logger.logError(TAG, "Bundled Manager installation failed: " + e.toString());
        }
    }

    private static void installChecked(Context context) throws IOException {
        File files = context.getFilesDir();
        File home = new File(files, "home");
        File parent = new File(home, "scripts");
        File target = new File(parent, "manager");
        if (!new File(files, "usr/bin").isDirectory()) {
            // Do not attempt setup before the official bootstrap finishes.
            throw new IOException("Termux bootstrap binaries not yet installed");
        }
        if (!mkdirs(home) || !mkdirs(parent)) {
            throw new IOException("Cannot create Manager directories");
        }
        // Do not follow a symlink that points outside the home scripts directory.
        String parentCanonical = parent.getCanonicalPath() + File.separator;
        if (!target.getCanonicalPath().startsWith(parentCanonical)) {
            throw new IOException("Manager path is outside home scripts directory");
        }

        Map<String, String> index = readIndex(context);
        boolean managed = new File(target, INSTALLED_MARKER).isFile();
        // For an existing managed installation, compare the installed index to
        // the new index; only unmodified old files may be replaced. Untracked
        // user installations are always left intact.
        boolean needsUpdate = !target.exists() || (managed &&
                (!index.equals(readPreviousIndex(context, target)) ||
                 needsManagedRepair(target, index)));
        if (needsUpdate) {
            File staging = File.createTempFile(".termux-manager-stage-", ".tmp", parent);
            if (!staging.delete() || !staging.mkdir()) {
                throw new IOException("Cannot initialize temporary Manager directory");
            }
            boolean committed = false;
            try {
                extractSafeZip(context.getAssets().open(ZIP_ASSET), staging, index);
                File main = new File(staging, "manager.sh");
                main.setReadable(true, true);
                main.setExecutable(true, true);
                if (!target.exists()) {
                    writeFile(new File(staging, INSTALLED_MARKER), "bundled\n", false);
                    writeFile(new File(staging, VERSION_INDEX_MARKER), serializeIndex(index), false);
                    if (!staging.renameTo(target)) throw new IOException("Cannot commit Manager directory");
                    committed = true;
                } else if (managed && target.isDirectory()) {
                    Map<String, String> previous = readPreviousIndex(context, target);
                    restoreAndUpgrade(staging, target, previous, index);
                    // Commit the baseline last. Even if a file is user-edited,
                    // it stays untouched because its hash will not match this.
                    writeFile(new File(target, VERSION_INDEX_MARKER), serializeIndex(index), false);
                }
            } finally {
                if (!committed) deleteRecursively(staging);
            }
        }

        File script = new File(target, "manager.sh");
        if (script.isFile()) {
            File bin = new File(files, "usr/bin");
            makeShortcut(new File(bin, "manager"), script);
            makeShortcut(new File(bin, "mm"), script);
            makeAutostartControl(new File(bin, "manager-autostart"));
            configureShellAutostart(home);
            Logger.logInfo(TAG, "Bundled Manager available without Internet");
        } else {
            Logger.logError(TAG, "Manager folder exists without manager.sh; user files preserved");
        }
        configurePowerShellPalette(home);
    }

    private static void configurePowerShellPalette(File home) throws IOException {
        File termux = new File(home, ".termux");
        if (!mkdirs(termux)) throw new IOException("Cannot create .termux theme folder");
        File colors = new File(termux, "colors.properties");
        if (!colors.exists()) {
            writeFile(colors, TERMINAL_PALETTE, false);
            Logger.logInfo(TAG, "Applied default Windows PowerShell blue terminal palette");
        }
    }

    private static boolean needsManagedRepair(File target, Map<String, String> index) {
        if (!target.isDirectory() || !new File(target, INSTALLED_MARKER).isFile()) return false;
        for (String path : index.keySet()) {
            if (!new File(target, path).isFile()) return true;
        }
        return false;
    }

    private static String serializeIndex(Map<String, String> index) {
        java.util.List<String> names = new java.util.ArrayList<>(index.keySet());
        java.util.Collections.sort(names);
        StringBuilder result = new StringBuilder();
        for (String name : names) result.append(name).append('\t').append(index.get(name)).append('\n');
        return result.toString();
    }

    private static Map<String, String> parseIndex(String source) throws IOException {
        Map<String, String> index = new HashMap<>();
        for (String line : source.split("\n")) {
            if (line.isEmpty()) continue;
            String[] pieces = line.split("\t", -1);
            if (pieces.length != 2 || !isSafeName(pieces[0]) ||
                    !pieces[1].matches("[0-9a-f]{64}") || index.put(pieces[0], pieces[1]) != null) {
                throw new IOException("Malformed Manager index");
            }
        }
        return index;
    }

    private static Map<String, String> readPreviousIndex(Context context, File target) throws IOException {
        File marker = new File(target, VERSION_INDEX_MARKER);
        if (marker.isFile()) return parseIndex(readSmallText(marker));
        // alpha.3 had a bundled marker but did not retain per-file hashes.
        // This independently packed index is the baseline of that release.
        try (InputStream in = context.getAssets().open(LEGACY_INDEX_ASSET)) {
            java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (output.size() + n > 256 * 1024) throw new IOException("Legacy index too large");
                output.write(buffer, 0, n);
            }
            return parseIndex(new String(output.toByteArray(), StandardCharsets.UTF_8));
        }
    }

    private static void restoreAndUpgrade(File staged, File target,
                    Map<String, String> previous, Map<String, String> current) throws IOException {
        String base = target.getCanonicalPath() + File.separator;
        for (Map.Entry<String, String> entry : current.entrySet()) {
            String name = entry.getKey();
            File destination = new File(target, name);
            if (!destination.getCanonicalPath().startsWith(base)) throw new IOException("Unsafe update path");
            File source = new File(staged, name);
            if (!destination.exists()) {
                safelyReplaceFile(source, destination);
            } else if (destination.isFile() && previous.containsKey(name) &&
                    previous.get(name).equals(sha256(destination)) &&
                    !entry.getValue().equals(sha256(destination))) {
                safelyReplaceFile(source, destination);
            } // User-changed or untracked files are preserved.
        }
    }

    private static void safelyReplaceFile(File source, File destination) throws IOException {
        if (!mkdirs(destination.getParentFile())) throw new IOException("Cannot create Manager subdirectory");
        File candidate = File.createTempFile(".tm-install-", ".tmp", destination.getParentFile());
        try {
            try (InputStream input = new FileInputStream(source);
                 OutputStream output = new FileOutputStream(candidate)) {
                byte[] data = new byte[8192];
                int n;
                while ((n = input.read(data)) != -1) output.write(data, 0, n);
            }
            if (destination.exists()) {
                File backup = File.createTempFile(".tm-backup-", ".tmp", destination.getParentFile());
                if (!backup.delete() || !destination.renameTo(backup)) {
                    throw new IOException("Cannot backup existing managed file: " + destination);
                }
                if (!candidate.renameTo(destination)) {
                    if (!backup.renameTo(destination)) throw new IOException("Could not restore backup: " + backup);
                    throw new IOException("Could not upgrade managed file: " + destination);
                }
                if (!backup.delete()) Logger.logError(TAG, "Could not delete backup " + backup);
            } else if (!candidate.renameTo(destination)) {
                throw new IOException("Cannot commit managed file: " + destination);
            }
            if (destination.getName().endsWith(".sh")) destination.setExecutable(true, true);
        } finally {
            candidate.delete();
        }
    }

    private static Map<String, String> readIndex(Context context) throws IOException {
        Map<String, String> index = new HashMap<>();
        try (InputStream in = context.getAssets().open(INDEX_ASSET)) {
            byte[] data = new byte[256 * 1024 + 1];
            int count = 0, n;
            while ((n = in.read(data, count, data.length - count)) != -1) {
                count += n;
                if (count == data.length) throw new IOException("Manager index too large");
            }
            String str = new String(data, 0, count, StandardCharsets.UTF_8);
            for (String line : str.split("\n")) {
                if (line.isEmpty()) continue;
                String[] pieces = line.split("\t", -1);
                if (pieces.length != 2 || !isSafeName(pieces[0]) ||
                        !pieces[1].matches("[0-9a-f]{64}") ||
                        index.put(pieces[0], pieces[1]) != null) {
                    throw new IOException("Malformed Manager bundle index");
                }
            }
        }
        if (index.isEmpty() || index.size() > MAX_ENTRIES ||
                !index.containsKey("MANIFEST.json") || !index.containsKey("manager.sh") ||
                !index.containsKey("modules/core.sh")) {
            throw new IOException("Manager bundle index is incomplete");
        }
        return index;
    }

    private static boolean isSafeName(String name) {
        if (name.isEmpty() || name.startsWith("/") || name.indexOf('\\') >= 0 ||
                name.indexOf('\t') >= 0 || name.indexOf('\n') >= 0) return false;
        for (String part : name.split("/")) {
            if (part.isEmpty() || part.equals(".") || part.equals("..")) return false;
        }
        return true;
    }

    private static String sha256(File file) throws IOException {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[8192];
            try (InputStream in = new FileInputStream(file)) {
                int n;
                while ((n = in.read(buffer)) != -1) md.update(buffer, 0, n);
            }
            StringBuilder sb = new StringBuilder();
            for (byte value : md.digest()) {
                sb.append(Character.forDigit((value >>> 4) & 15, 16));
                sb.append(Character.forDigit(value & 15, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IOException("SHA-256 unavailable", e);
        }
    }

    private static void extractSafeZip(InputStream source, File root,
                                       Map<String, String> index) throws IOException {
        byte[] buffer = new byte[8192];
        String rootCanonical = root.getCanonicalPath() + File.separator;
        long totalBytes = 0;
        int entries = 0;
        Set<String> seen = new HashSet<>();
        try (ZipInputStream input = new ZipInputStream(new BufferedInputStream(source))) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                if (++entries > MAX_ENTRIES) throw new IOException("Too many Manager bundle entries");
                String name = entry.getName();
                // The packaged ZIP has files only, not directory placeholders.
                if (entry.isDirectory() || !isSafeName(name) ||
                        !index.containsKey(name) || !seen.add(name)) {
                    throw new IOException("Unknown, duplicate or invalid Manager bundle entry: " + name);
                }
                File destination = new File(root, name);
                String canonical = destination.getCanonicalPath();
                if (!canonical.startsWith(rootCanonical)) throw new IOException("Manager bundle path escapes extraction root");
                if (!mkdirs(destination.getParentFile())) throw new IOException("Cannot create Manager bundle parent");
                try (OutputStream output = new BufferedOutputStream(new FileOutputStream(destination))) {
                    int bytes;
                    while ((bytes = input.read(buffer)) != -1) {
                        totalBytes += bytes;
                        if (totalBytes > MAX_UNCOMPRESSED_BYTES) throw new IOException("Manager bundle too large");
                        output.write(buffer, 0, bytes);
                    }
                }
                if (!index.get(name).equals(sha256(destination))) {
                    throw new IOException("Manager bundle SHA-256 mismatch: " + name);
                }
                if (name.endsWith(".sh")) destination.setExecutable(true, true);
                input.closeEntry();
            }
        }
        if (!seen.equals(index.keySet())) throw new IOException("Missing Manager bundle entries");
    }

    private static void makeShortcut(File shortcut, File manager) throws IOException {
        if (shortcut.exists()) return; // Never overwrite a user command.
        String script = "#!/data/data/com.termux/files/usr/bin/bash\n"
            + "# AL_MANAGER_SHORTCUT - bundled TermuxManager\n"
            + "exec /data/data/com.termux/files/usr/bin/bash \"" + manager.getAbsolutePath() + "\" \"$@\"\n";
        writeFile(shortcut, script, false);
        shortcut.setExecutable(true, false);
    }

    private static void makeAutostartControl(File command) throws IOException {
        if (command.exists()) return;
        String script = "#!/data/data/com.termux/files/usr/bin/bash\n"
            + "# Termux Manager: control optional Bash autostart.\n"
            + "case \"${1:-status}\" in\n"
            + "  disable) touch \"$HOME/.termux-manager-no-autostart\" ;;\n"
            + "  enable) rm -f \"$HOME/.termux-manager-no-autostart\" ;;\n"
            + "  status) if [ -e \"$HOME/.termux-manager-no-autostart\" ]; then echo disabled; else echo enabled; fi ;;\n"
            + "  remove)\n"
            + "    profile=\"$HOME/.bash_profile\"\n"
            + "    [ -f \"$profile\" ] || exit 0\n"
            + "    tmp=\"$profile.tm.$$\"\n"
            + "    (umask 077; : > \"$tmp\") || exit 1\n"
            + "    skipping=0\n"
            + "    while IFS= read -r line || [ -n \"$line\" ]; do\n"
            + "      if [ \"$line\" = '# TERMUX_MANAGER_BUNDLE_AUTOSTART_V1' ]; then skipping=1; continue; fi\n"
            + "      if [ \"$line\" = '# TERMUX_MANAGER_BUNDLE_AUTOSTART_END_V1' ] && [ \"$skipping\" = 1 ]; then skipping=0; continue; fi\n"
            + "      if [ \"$skipping\" = 0 ]; then printf '%s\\n' \"$line\" >> \"$tmp\"; fi\n"
            + "    done < \"$profile\"\n"
            + "    if [ \"$skipping\" = 1 ]; then rm -f \"$tmp\"; echo 'Profile marker not closed' >&2; exit 1; fi\n"
            + "    mv -f \"$tmp\" \"$profile\"\n"
            + "    ;;\n"
            + "  *) echo 'Usage: manager-autostart [status|disable|enable|remove]' >&2; exit 2 ;;\n"
            + "esac\n";
        writeFile(command, script, false);
        command.setExecutable(true, true);
    }

    private static void configureShellAutostart(File home) throws IOException {
        File profile = new File(home, ".bash_profile");
        if (profile.exists() && !profile.isFile()) return;
        String existing = profile.isFile() ? readSmallText(profile) : "";
        if (existing.contains(AUTOSTART_MARKER)) return;
        String append = "\n" + AUTOSTART_MARKER + "\n"
            + "# Keep Bash available after the manager exits.\n"
            + "case $- in *i*)\n"
            + "  if [ -t 0 ] && [ -z \"${TERMUX_MANAGER_DISABLE_AUTOSTART:-}\" ] "
            + "&& [ -z \"${TERMUX_MANAGER_AUTOSTARTED:-}\" ] "
            + "&& [ ! -e \"$HOME/.termux-manager-no-autostart\" ] "
            + "&& [ -r \"$HOME/scripts/manager/manager.sh\" ]; then\n"
            + "    export TERMUX_MANAGER_AUTOSTARTED=1\n"
            + "    export TERMUX_MANAGER_GITHUB_RAW_BASE=https://raw.githubusercontent.com/drilemoz/TermuxManager/main\n"
            + "    export TERMUX_MANAGER_GITHUB_ARCHIVE_URL=https://github.com/drilemoz/TermuxManager/archive/refs/heads/main.zip\n"
            + "    bash \"$HOME/scripts/manager/manager.sh\"\n"
            + "  fi\n"
            + "  ;;\n"
            + "esac\n"
            + "# TERMUX_MANAGER_BUNDLE_AUTOSTART_END_V1\n";
        // Preserve existing login configuration and append at the end.
        writeFile(profile, existing + append, false);
    }

    private static String readSmallText(File file) throws IOException {
        if (file.length() > 256 * 1024) throw new IOException("Shell profile is unexpectedly large");
        byte[] bytes = new byte[(int) file.length()];
        try (InputStream input = new FileInputStream(file)) {
            int filled = 0;
            while (filled < bytes.length) {
                int n = input.read(bytes, filled, bytes.length - filled);
                if (n < 0) break;
                filled += n;
            }
            if (filled != bytes.length) throw new IOException("Cannot read shell profile fully");
        }
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private static void writeFile(File file, String text, boolean append) throws IOException {
        try (FileOutputStream output = new FileOutputStream(file, append)) {
            output.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }

    private static boolean mkdirs(File file) {
        return file.isDirectory() || file.mkdirs();
    }

    private static void deleteRecursively(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursively(child);
        }
        file.delete();
    }
}
