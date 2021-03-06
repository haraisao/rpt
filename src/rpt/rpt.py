#
#
import sys,os
import signal
import ros4win as r4w
import traceback

signal.signal(signal.SIGINT, signal.SIG_DFL)
cmds=[]

#
# 
def getArgCwd(n):
  if len(sys.argv) > n: res=sys.argv[n]
  else: res=os.getcwd()[:2]
  return res

#
#
def install_pkg():
  name = sys.argv[2]
  drv = getArgCwd(3)
  r4w.install_package_all(name, drv)
#cmds.append(install_pkg)

#
#
def inst():
  name = sys.argv[2]
  drv = getArgCwd(3)
  r4w.install_package(name, drv, False, True)
#cmds.append(inst)

#
#
def get_hash():
  file_name = sys.argv[2]
  res=r4w.get_hash_value(file_name)

  print(os.path.basename(file_name), res)
#cmds.append(get_hash)

#
#
def installed_pkgs():
  drv = getArgCwd(2)
  res=r4w.get_installed_pkgs(drv)
  for x in res:
    print(x)
#cmds.append(installed_pkgs)

def getRptDir():
  if 'RPT_HOME' in os.environ and os.environ['RPT_HOME']:
    return os.environ['RPT_HOME']
  dirname=os.path.dirname(os.path.abspath(__file__))
  seq=dirname.split(os.path.sep)
  if (os.path.splitext(seq.pop())[1] == ".pyz" ):
    return os.path.sep.join(seq)
  else:
    return dirname

#
#
def installed_files():
  name=sys.argv[2]
  drv = getArgCwd(3)
  dbname=r4w.default_pkgmgr_db(drv)
  res=r4w.select_install_info(name, dbname)
  for x in res:
    print(x)
#cmds.append(installed_files)


#
#
def check():
  drv = getArgCwd(3)
  pname=sys.argv[2]
  try:
    lst=package_list(drv)
    res = pname in lst
    if res:
      print(pname, "OK")
    else:
      print("--")
    return res
  except:
    print("No package")
    return False
cmds.append(check)



#
#
def pkg_dep():
  pkg_name=sys.argv[2]
  res=r4w.get_pkg_dep(pkg_name)
  print(res)
#cmds.append(pkg_dep)

#
#
def pkg_list():
  pkg_name=sys.argv[2]
  res=r4w.get_pkg_list(pkg_name)
  print(res)
#cmds.append(pkg_list)

#
#
def pkgname():
  file_name=sys.argv[2]
  print(r4w.file_to_pkgname( file_name ).split(','))
#cmds.append(pkgname)

#
#
def package_list(drv):
  dbname=r4w.default_pkgmgr_db(drv)
  try:
    res=r4w.select_pkg_data('all', dbname)
    lst={}
    for x in res:
      lst[x[0]]=x[4]
    return lst
  except:
    return []

#
#
def list():
  drv = getArgCwd(2)
  try:
    lst=package_list(drv)
    lst=sorted(lst.items())

    for x in lst:
      print("   - "+x[0])
    return lst
  except:
    print("No package")
    return []
cmds.append(list)

#
#
def update():
  drv = getArgCwd(2)
  update_cache()
  try:
    lst=package_list(drv)
    lst_pkg=r4w.load_pkg_hash(getRptDir()+"\\__pkg__\\pkgs.yaml")
    #print(lst)
    res=[]
    for x in lst:
      try:
        if lst_pkg[x] != lst[x]:
          res.append(x.split(',')[0])
      except:
        print("== ERROR: no such package [",x, "]")
    if len(res):
      print("[%s]" % ",".join(res))
      print(" %d updates..." % len(res))
    else:
      print("No update")
  except:
    traceback.print_exc()
    print("Update package list")
cmds.append(update)

#
def upgrade():
  drv = getArgCwd(2)
  lst=package_list(drv)
  lst_pkg=r4w.load_pkg_hash(getRptDir()+"\\__pkg__\\pkgs.yaml")

  res=[]
  for x in lst:
    if lst_pkg[x] != lst[x]:
      res.append(x.split(',')[0])
  if len(res) == 0 :
    print("No upgradable package")
    return
  print("[%s]" % ",".join(res))
  print(" %d packages, update ? (Y/n) " % len(res), end="")
  str=input().strip()
  if str == "n":
    print("...Canceled")
  else:
    print("Start upgrade packages")
    files=[]
    path= getRptDir()+"\\ros_pkg"
    for name in res:
      f=r4w.download_package_file(name, path)
      files.append(f)

    for name in res:
      print("remove package", name)
      r4w.remove_pkg_file_all(name, drv)

    for f in files:
      fname=path+"\\"+f
      print("Update file", fname)

      r4w.install_package(fname, drv, False, True)
cmds.append(upgrade)
#
#
def remove():
  pkg_name=sys.argv[2]
  drv = getArgCwd(3)
  r4w.remove_pkg_file_all(pkg_name, drv)
cmds.append(remove)

#
#
def update_cache(pkg_dir=None):
  if pkg_dir is None:  pkg_dir=getRptDir()+"\\__pkg__"
  r4w.download_package_file("list", pkg_dir)

#
#
def download(name="", path=None):
  if path is None:  path = getRptDir()+"\\ros_pkg"
  if not name : name=sys.argv[2]
  if len(sys.argv) > 3:  path=sys.argv[3]
  return r4w.download_package_file(name, path)
#cmds.append(download)

#
#
def download_all(path=None):
  if path is None:  path = getRptDir()+"\\ros_pkg"
  name=sys.argv[2]
  if len(sys.argv) > 3:  path=sys.argv[3]

  pkgs, info=r4w.get_depends(name)
  files=[]
  count=1
  n=len(pkgs)
  
  for x in pkgs:
    try:
      fname=r4w.download_package_file(x, path)
      #fname=r4w.pkgname_to_file(x)
      files.append(fname)
      v=r4w.getMonDots(count)
      y=int(count/n * 100)
      print("Download: %s  [%d]%%\r" % (v, y), end="", flush=True)
    except:
      print("ERROR: [", x, "]                   ", flush=True)
      pass
    count += 1
  return files
#cmds.append(download_all)

#
#
def install(path=None):
  if path is None:  path = getRptDir()+"\\ros_pkg"
  files=download_all(path)
  print("Finish downloading files....")
  n=len(files)
  dname=os.getcwd()[:2]
  to_pkgdir=dname+"\\opt"
  count=1

  for fname in files:
    ff=r4w.file_to_pkgname(fname, getRptDir()+"\\__pkg__\\pkgs.yaml")
    v=r4w.getMonChar(count)
    y=int(count/n * 100)
    if not r4w.check_pkg_installed(fname, to_pkgdir):
      r4w.install_package(path+"/"+fname, dname, None, False)
    print("\rInstall: %s  [%d]%%\r" % (v, y), end="", flush=True)
    count += 1
cmds.append(install)

#
#
def all_package():
  name=sys.argv[2]
  pkgs, info=r4w.get_depends(name)
  pkg=[]
  no_pkg=[]
  keys=list(info.keys())
  for x in pkgs:
    if x in keys:  pkg.append(x)
    else:    no_pkg.append(x)
  print()
  print("Package:", ",".join(pkg))
  print()
  print("No package:", ",".join(no_pkg))
#cmds.append(all_package)

#
#
def get_pkg(path=""):
  names=sys.argv[2].split(":")
  if len(sys.argv) > 3:  path=sys.argv[3]

  for n in names:
    if r4w.is_meta_pkg(n):
      res=r4w.get_pkg_list(n)
      if res :
        r4w.get_pkgs(list(res.keys()), path)
    else:
      r4w.download_package_file(n, path)
#cmds.append(get_pkg)

#
#
def search():
  name=sys.argv[2]
  lst=r4w.load_pkg_list(getRptDir()+"\\__pkg__\\pkgs.yaml")
  try:
    for x in lst:
      if name in x or name in lst[x]['description']:
        print(r4w.Fore.GREEN + "\n"+ x +":")
        print("      "+lst[x]['description'].strip())
  except:
    print("No such package", name)
cmds.append(search)

#
#
cmds_str=[x.__name__ for x in cmds]

usage="Usage: %s cmd [arg1 arg2 ...]\n" % os.path.basename(sys.argv[0])
usage+= "   cmd: "+", ".join(cmds_str)



def main():
  if len(sys.argv) < 2:
    print(usage)
    sys.exit()
  try:
    res=False
    cmd=sys.argv[1]
    for fn in cmds:
      if fn.__name__ == cmd:
        fn()
        res=True
    if not res :
      print(usage)
  except:
    traceback.print_exc()
    print("Error...")

##############################
#  M A I N
#

if __name__ == '__main__':
  main()

