#!/usr/bin/env python3
"""Compile and exercise the Android-independent Java bundle logic using stubs."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        src=td/'src'
        for pkg in ['android/content','android/content/res','com/termux/shared/logger','com/termux/app']:
            (src/pkg).mkdir(parents=True)
        (src/'android/content/Context.java').write_text('''package android.content;
import java.io.File;
import android.content.res.AssetManager;
public class Context {
    private final File files;
    private final AssetManager assets;
    public Context(File files, AssetManager assets) {this.files=files;this.assets=assets;}
    public File getFilesDir() {return files;}
    public AssetManager getAssets() {return assets;}
}''')
        (src/'android/content/res/AssetManager.java').write_text('''package android.content.res;
import java.io.*;
public class AssetManager {
    private final File data;
    public AssetManager(File data) {this.data=data;}
    public InputStream open(String name) throws IOException {return new FileInputStream(new File(data,name));}
}''')
        (src/'com/termux/shared/logger/Logger.java').write_text('''package com.termux.shared.logger;
public class Logger {
    public static void logInfo(String a,String b){System.out.println("info:"+a+":"+b);}
    public static void logError(String a,String b){System.err.println("error:"+a+":"+b);}
}''')
        shutil.copyfile(ROOT/'integration/TermuxManagerBundle.java',src/'com/termux/app/TermuxManagerBundle.java')
        (src/'com/termux/app/TestBundle.java').write_text('''package com.termux.app;
import android.content.Context;
import android.content.res.AssetManager;
import java.io.*;
import java.nio.file.Files;
public class TestBundle {
  public static void main(String[] args) throws Exception {
    File files=new File(args[0]);files.mkdirs();
    File home=new File(files,"home");home.mkdirs();
    File profile=new File(home,".bash_profile");
    Files.write(profile.toPath(), "export HELLO=world\\n".getBytes("UTF-8"));
    Context ctx=new Context(files,new AssetManager(new File(args[1])));
    TermuxManagerBundle.install(ctx);
    File manager=new File(files,"home/scripts/manager/manager.sh");
    if(!manager.isFile())throw new RuntimeException("missing manager");
    File shortcut=new File(files,"usr/bin/manager");
    if(!shortcut.canExecute())throw new RuntimeException("missing shortcut");
    String profileText=new String(Files.readAllBytes(profile.toPath()),"UTF-8");
    if(!profileText.contains("export HELLO=world"))throw new RuntimeException("profile clobbered");
    if(!profileText.contains("TERMUX_MANAGER_BUNDLE_AUTOSTART_V1"))throw new RuntimeException("missing autostart");
    Files.write(manager.toPath(), "user edits\\n".getBytes("UTF-8"));
    TermuxManagerBundle.install(ctx);
    if(!new String(Files.readAllBytes(manager.toPath()),"UTF-8").equals("user edits\\n"))
      throw new RuntimeException("modified manager overwritten");
    if(new String(Files.readAllBytes(profile.toPath()),"UTF-8").split("TERMUX_MANAGER_BUNDLE_AUTOSTART_V1",-1).length!=2)
      throw new RuntimeException("profile patched twice");
    System.out.println("JAVA_BUNDLE_OK");
  }
}''')
        assets=td/'assets';assets.mkdir()
        with zipfile.ZipFile(assets/'termux-manager.bundle.zip','w') as z:
            z.writestr('manager.sh','#!/bin/sh\n')
            z.writestr('MANIFEST.json','{}')
            z.writestr('modules/core.sh','echo hi\n')
        java_files=[str(x) for x in src.rglob('*.java')]
        (td/'classes').mkdir()
        subprocess.run(['javac','--release','8','-d',str(td/'classes'),*java_files],check=True)
        r=subprocess.run(['java','-cp',str(td/'classes'),'com.termux.app.TestBundle',str(td/'files'),str(assets)],text=True,capture_output=True,check=True)
        print(r.stdout.strip())
        # A malicious ZIP entry must not escape the installation directory.
        (td/'files2').mkdir()
        with zipfile.ZipFile(assets/'termux-manager.bundle.zip','w') as z:
            z.writestr('../escape.sh','bad')
            z.writestr('manager.sh','#!/bin/sh\n')
            z.writestr('MANIFEST.json','{}')
            z.writestr('modules/core.sh','echo hi\n')
        r=subprocess.run(['java','-cp',str(td/'classes'),'com.termux.app.TestBundle',str(td/'files2'),str(assets)],text=True,capture_output=True)
        if r.returncode == 0 or (td/'files2/home/scripts/escape.sh').exists():
            raise RuntimeError('Zip slip was not rejected')
        print('JAVA_ZIP_SLIP_OK')


if __name__=='__main__':
    main()
