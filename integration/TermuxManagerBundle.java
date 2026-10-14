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
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Offline installation of a bundled copy of TermuxManager after the stock Termux
 * bootstrap has been extracted. This is not a replacement for the bootstrap.
 *
 * The bundle is installed only if no Manager installation exists. A user's
 * modified files will never be overwritten by an APK installation.
 */
final class TermuxManagerBundle {
    private static final String TAG = "TermuxManagerBundle";
    private static final String ZIP_ASSET = "termux-manager.bundle.zip";
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
        if (!mkdirs(parent)) throw new IOException("Cannot create Manager parent directory");

        if (!target.exists()) {
            File staging = File.createTempFile(".termux-manager-stage-", ".tmp", parent);
            if (!staging.delete() || !staging.mkdir()) {
                throw new IOException("Cannot initialize temporary Manager directory");
            }
            boolean committed = false;
            try {
                extractSafeZip(context.getAssets().open(ZIP_ASSET), staging);
                if (!new File(staging, "manager.sh").isFile() ||
                    !new File(staging, "MANIFEST.json").isFile() ||
                    !new File(staging, "modules/core.sh").isFile()) {
                    throw new IOException("Bundled Manager has missing mandatory files");
                }
                new File(staging, "manager.sh").setReadable(true, true);
                new File(staging, "manager.sh").setExecutable(true, true);
                // Another installer or user could have created the target.
                if (!target.exists()) {
                    if (!staging.renameTo(target)) throw new IOException("Cannot commit Manager directory");
                    committed = true;
                }
            } finally {
                if (!committed) deleteRecursively(staging);
            }
        }

        File script = new File(target, "manager.sh");
        if (!script.isFile()) return;
        File bin = new File(files, "usr/bin");
        if (!mkdirs(bin)) throw new IOException("Cannot access Termux binaries directory");
        makeShortcut(new File(bin, "manager"), script);
        makeShortcut(new File(bin, "mm"), script);
        configureShellAutostart(home);
        Logger.logInfo(TAG, "Bundled Manager installed (no Internet required)");
    }

    private static void extractSafeZip(InputStream source, File root) throws IOException {
        byte[] buffer = new byte[8192];
        String rootCanonical = root.getCanonicalPath() + File.separator;
        long totalBytes = 0;
        int entries = 0;
        try (ZipInputStream input = new ZipInputStream(new BufferedInputStream(source))) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                if (++entries > MAX_ENTRIES) throw new IOException("Too many Manager bundle entries");
                String name = entry.getName();
                if (name.isEmpty() || name.startsWith("/") || name.indexOf('\\') >= 0) {
                    throw new IOException("Invalid Manager bundle path");
                }
                File destination = new File(root, name);
                String canonical = destination.getCanonicalPath();
                if (!canonical.startsWith(rootCanonical)) throw new IOException("Manager bundle path escapes extraction root");
                if (entry.isDirectory()) {
                    if (!mkdirs(destination)) throw new IOException("Cannot create Manager bundle directory");
                } else {
                    if (!mkdirs(destination.getParentFile())) throw new IOException("Cannot create Manager bundle parent");
                    try (OutputStream output = new BufferedOutputStream(new FileOutputStream(destination))) {
                        int bytes;
                        while ((bytes = input.read(buffer)) != -1) {
                            totalBytes += bytes;
                            if (totalBytes > MAX_UNCOMPRESSED_BYTES) throw new IOException("Manager bundle too large");
                            output.write(buffer, 0, bytes);
                        }
                    }
                }
                input.closeEntry();
            }
        }
        if (entries == 0) throw new IOException("Empty Manager bundle");
    }

    private static void makeShortcut(File shortcut, File manager) throws IOException {
        if (shortcut.exists()) return; // Never overwrite a user command.
        String script = "#!/data/data/com.termux/files/usr/bin/bash\n"
            + "# AL_MANAGER_SHORTCUT - bundled TermuxManager\n"
            + "exec /data/data/com.termux/files/usr/bin/bash \"" + manager.getAbsolutePath() + "\" \"$@\"\n";
        writeFile(shortcut, script, false);
        shortcut.setExecutable(true, false);
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
            + "esac\n";
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
