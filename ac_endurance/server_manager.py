"""Read-only Assetto Corsa installation inspection and guarded LinuxGSM restart."""
from __future__ import annotations
import configparser, os, shutil, subprocess, time, zipfile
from pathlib import Path

class ServerManager:
    def __init__(self,root:str|None=None,lgsm:str|None=None,backup_dir:str|None=None):
        install_root=Path(__file__).resolve().parents[1]
        host_root=install_root.parent
        self.root=Path(root or os.getenv("ACEC_SERVER_ROOT",str(host_root/"serverfiles"))).resolve()
        self.lgsm=Path(lgsm or os.getenv("ACEC_LGSM",str(host_root/"acserver"))).resolve()
        self.backup_dir=Path(backup_dir or os.getenv("ACEC_BACKUP_DIR",str(install_root/"var"/"backups"))).resolve()
    def process_ids(self)->list[int]:
        found=[]
        proc=Path("/proc")
        for entry in proc.iterdir():
            if not entry.name.isdigit(): continue
            try:
                command=(entry/"cmdline").read_bytes().replace(b"\0",b" ").decode(errors="ignore")
                cwd=os.readlink(entry/"cwd")
                if "acServer" in command and str(self.root) in (command+" "+cwd): found.append(int(entry.name))
            except (OSError,PermissionError): continue
        return sorted(set(found))
    def config(self)->dict:
        p=self.root/"cfg"/"server_cfg.ini"
        if not p.is_file(): return {"detected":False,"root":str(self.root)}
        parser=configparser.ConfigParser(interpolation=None,strict=False); parser.read(p,encoding="utf-8")
        main=parser["SERVER"] if parser.has_section("SERVER") else {}
        return {"detected":(self.root/"acServer").is_file(),"root":str(self.root),"config":str(p),
                "name":main.get("NAME"),"track":main.get("TRACK"),"track_config":main.get("CONFIG_TRACK"),
                "udp_port":main.get("UDP_PORT"),"tcp_port":main.get("TCP_PORT"),
                "udp_plugin_enabled":main.get("UDP_PLUGIN_LOCAL_PORT","0") not in ("0",""),
                "cars":self.catalog("cars"),"tracks":self.catalog("tracks"),"process_ids":self.process_ids(),
                "linuxgsm":str(self.lgsm) if self.lgsm.is_file() else None}
    def catalog(self,kind:str)->list[str]:
        folder=self.root/"content"/kind
        return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []
    def backup(self)->str:
        cfg=self.root/"cfg"
        if not cfg.is_dir(): raise FileNotFoundError(f"Brak katalogu konfiguracji: {cfg}")
        self.backup_dir.mkdir(parents=True,exist_ok=True)
        out=self.backup_dir/f"ac-config-{time.strftime('%Y%m%d-%H%M%S',time.gmtime())}.zip"
        tmp=out.with_suffix(".tmp")
        with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:
            for p in cfg.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(self.root))
        os.replace(tmp,out)
        return str(out)
    def restart(self,timeout:int=120)->dict:
        pids=self.process_ids()
        if len(pids)>1: raise RuntimeError(f"Wykryto wiele procesów acServer dla tej instalacji: {pids}; restart zablokowany")
        if not pids: raise RuntimeError("Serwer nie działa; restart nie uruchomi nowej instancji")
        if not self.lgsm.is_file() or not os.access(self.lgsm,os.X_OK): raise RuntimeError("Nie znaleziono wykonywalnego skryptu LinuxGSM")
        backup=self.backup()
        result=subprocess.run([str(self.lgsm),"restart"],cwd=str(self.lgsm.parent),capture_output=True,text=True,timeout=timeout,check=False)
        after=self.process_ids()
        if result.returncode!=0: raise RuntimeError(f"LinuxGSM restart zakończył się kodem {result.returncode}; kopia: {backup}")
        if len(after)>1: raise RuntimeError(f"Po restarcie wykryto wiele procesów acServer: {after}; kopia: {backup}")
        return {"backup":backup,"before":pids,"after":after,"returncode":result.returncode}
