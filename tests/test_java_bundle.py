#!/usr/bin/env python3
"""Compile installer with Android stubs and exercise ZIP hash safety and repair."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_assets(folder: Path, extras=None, *, bad_hash=False):
    files = {
        'manager.sh': b'#!/bin/sh\necho ok\n',
        'modules/core.sh': b'echo core\n',
        'install.sh': b'#!/bin/sh\n',
        'MANIFEST.json': b'{}',
    }
    entries = {key: hashlib.sha256(value).hexdigest() for key, value in files.items()}
    if bad_hash:
        entries['manager.sh'] = '0' * 64
    (folder / 'termux-manager.bundle-index.tsv').write_text(
        ''.join(f'{name}\t{digest}\n' for name, digest in sorted(entries.items())))
    with zipfile.ZipFile(folder / 'termux-manager.bundle.zip', 'w') as z:
        for key, value in files.items():
            z.writestr(key, value)
        for key, value in (extras or {}).items():
            z.writestr(key, value)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / 'src'
        for pkg in ['android/content', 'android/content/res', 'com/termux/shared/logger', 'com/termux/app']:
            (src / pkg).mkdir(parents=True)
        (src / 'android/content/Context.java').write_text('''package android.content;
import java.io.File;
import android.content.res.AssetManager;
public class Context {
  private final File files;
  private final AssetManager assets;
  public Context(File files,AssetManager assets){this.files=files;this.assets=assets;}
  public File getFilesDir(){return files;}
  public AssetManager getAssets(){return assets;}
}''')
        (src / 'android/content/res/AssetManager.java').write_text('''package android.content.res;
import java.io.*;
public class AssetManager {
  private final File data;
  public AssetManager(File data){this.data=data;}
  public InputStream open(String name)throws IOException{return new FileInputStream(new File(data,name));}
}''')
        (src / 'com/termux/shared/logger/Logger.java').write_text('''package com.termux.shared.logger;
public class Logger {
  public static void logInfo(String a,String b){System.out.println("info:"+a+":"+b);}
  public static void logError(String a,String b){System.err.println("error:"+a+":"+b);}
}''')
        shutil.copyfile(ROOT / 'integration/TermuxManagerBundle.java', src / 'com/termux/app/TermuxManagerBundle.java')
        (src / 'com/termux/app/TestBundle.java').write_text('''package com.termux.app;
import android.content.Context;
import android.content.res.AssetManager;
import java.io.*;
import java.nio.file.Files;
public class TestBundle {
 public static void main(String[]args)throws Exception {
  File files=new File(args[0]);new File(files,"home").mkdirs();new File(files,"usr/bin").mkdirs();
  File home=new File(files,"home");File profile=new File(home,".bash_profile");
  if(!profile.exists())Files.write(profile.toPath(),"export HELLO=world\\n".getBytes("UTF-8"));
  Context ctx=new Context(files,new AssetManager(new File(args[1])));
  TermuxManagerBundle.install(ctx);
  File manager=new File(files,"home/scripts/manager/manager.sh");
  if(!manager.isFile())throw new RuntimeException("missing manager");
  if(!new File(files,"usr/bin/manager").canExecute())throw new RuntimeException("missing shortcut");
  File palette=new File(home,".termux/colors.properties");
  if(!new String(Files.readAllBytes(palette.toPath()),"UTF-8").contains("#012456"))throw new RuntimeException("missing palette");
  String profileText=new String(Files.readAllBytes(profile.toPath()),"UTF-8");
  if(!profileText.contains("export HELLO=world")||!profileText.contains("TERMUX_MANAGER_BUNDLE_AUTOSTART_V1"))throw new RuntimeException("profile lost");
  Files.write(manager.toPath(),"user edits\\n".getBytes("UTF-8"));
  File missing=new File(files,"home/scripts/manager/modules/core.sh");
  if(!missing.delete())throw new RuntimeException("cannot simulate deleted module");
  Files.write(palette.toPath(),"background=#FFAA00\\n".getBytes("UTF-8"));
  TermuxManagerBundle.install(ctx);
  if(!missing.isFile())throw new RuntimeException("missing module not repaired");
  if(!new String(Files.readAllBytes(manager.toPath()),"UTF-8").equals("user edits\\n"))throw new RuntimeException("user edit overwritten");
  if(!new String(Files.readAllBytes(palette.toPath()),"UTF-8").contains("#FFAA00"))throw new RuntimeException("user palette overwritten");
  if(new String(Files.readAllBytes(profile.toPath()),"UTF-8").split("TERMUX_MANAGER_BUNDLE_AUTOSTART_V1",-1).length!=2)
      throw new RuntimeException("profile patched twice");
  System.out.println("JAVA_BUNDLE_OK");
 }
}''')
        (td / 'classes').mkdir()
        subprocess.run(['javac', '--release', '8', '-d', str(td / 'classes'),
                        *map(str, src.rglob('*.java'))], check=True)
        assets = td / 'assets'
        assets.mkdir()
        make_assets(assets)
        command = ['java', '-cp', str(td / 'classes'), 'com.termux.app.TestBundle']
        result = subprocess.run([*command, str(td / 'files'), str(assets)],
                                text=True, capture_output=True, check=True)
        assert 'JAVA_BUNDLE_OK' in result.stdout
        print('JAVA_BUNDLE_OK: theme, repair, user edits and profile preserved')
        control = td / 'files/usr/bin/manager-autostart'
        assert control.is_file()
        env = dict(os.environ, HOME=str(td / 'files/home'))
        subprocess.run(['bash', str(control), 'disable'], env=env, check=True)
        assert (td / 'files/home/.termux-manager-no-autostart').exists()
        subprocess.run(['bash', str(control), 'enable'], env=env, check=True)
        assert not (td / 'files/home/.termux-manager-no-autostart').exists()
        subprocess.run(['bash', str(control), 'remove'], env=env, check=True)
        result_profile = (td / 'files/home/.bash_profile').read_text()
        assert 'export HELLO=world' in result_profile
        assert 'TERMUX_MANAGER_BUNDLE_AUTOSTART' not in result_profile
        print('JAVA_AUTOSTART_COMMAND_OK')
        for label, extras, bad_hash in [
            ('ZIP_SLIP', {'../escape.sh': b'bad'}, False),
            ('UNLISTED_FILE', {'extra.sh': b'bad'}, False),
            ('CORRUPT_HASH', {}, True),
        ]:
            make_assets(assets, extras, bad_hash=bad_hash)
            files = td / ('files_' + label)
            result = subprocess.run([*command, str(files), str(assets)],
                                    text=True, capture_output=True)
            if result.returncode == 0 or (files.parent / 'escape.sh').exists():
                raise RuntimeError(label + ' not rejected: ' + result.stdout + result.stderr)
            print('JAVA_' + label + '_OK')


if __name__ == '__main__':
    main()
