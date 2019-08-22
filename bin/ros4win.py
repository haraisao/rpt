#
#  Package manager for Ros4Win
#     Copyright(C) 2019 Isao Hara
import os
import sys
import requests
import hashlib
import sqlite3
from contextlib import closing
import datetime
import tarfile
import glob
import re
import traceback
import shutil
import signal
import yaml
import re
import colorama
from colorama import Fore, Back, Style
import ros4win as r4w

colorama.init(autoreset=True)

PKG_LIST=['ros_base', 'ros_desktop', 'control', 'plan', 'navigation', 'robot']
LIB_LIST=['local', 'local-contrib', 'python', 'setup']
PKG_BASE_DIR="ros_pkg/"
PKG_PREFIX="ros-melodic-"
PKG_EXT=".tgz"

PKG_MGR_DIR="/opt/_pkgmgr"
PKG_DB="ros4win.db"

PKG_REPO_BASE="http://hara.jpn.com/cgi/"

PKG_MGR_DB="/opt/_pkgmgr/ros4win.db"

_mon=['-', '\\', '|', '/']
_mon2=['| ', ' ~', ' |', '_ ']
_mon_dot=['   ', '.  ', '.. ', '...', ' ..', '  .']
_mon_dot2=['    ', '>   ', '>>  ', '>>> ', '>>>>', ' >>>' '  >>', '   >']

def getMonChar(n):
  return _mon[ n % 4 ]

def getMonChar2(n):
  return _mon2[ n % 4 ]

def getMonDots(n):
  return _mon_dot[ n % 6 ]

def getMonDots2(n):
  return _mon_dot2[ n % 8 ]


#######
# Remote
#
def get_pkg_hash_value(name):
  url="%spkg_hash2.cgi?name=%s" % (PKG_REPO_BASE, name)
  res=requests.get(url)
  if res.status_code == 200:
    return res.text
  return ""
#
#
def get_attached_filename(response, filename, path=""):
  if 'Content-Disposition' in response.headers:
    val=response.headers['Content-Disposition']
    if "attachment" in val and "filename=" in val:
      filename=val.split('filename=')[-1]
  size=int(response.headers['Content-Length'])
  if path :
    if not os.path.exists(path) :
      os.makedirs(path)
    filename = path+"\\"+filename
  return filename, size
#  
#
def save_download_file(response, file_name, size, dl_chunk_size):
  #mon=['-', '\\', '|', '/']
  count = 1
  bs=10
  #
  # save to file
  with open(file_name, 'wb') as f:
    for chunk in response.iter_content(chunk_size=dl_chunk_size):
      f.write(chunk)
      remain = (size - dl_chunk_size * count) / size
      n = min(int((1-remain)*bs), bs)
      bar="=" * n + ">" + " " * (bs -n)
      print( "\rDownload %s:|%s|(%d%%) %s" % (os.path.basename(file_name), bar, min(100- remain*100, 100), getMonChar(count)), end="")
      count += 1
  return

def check_md5_file(h_val, fname):
  res=False
  if os.path.exists(fname):
    h_val2=get_hash_value(fname).strip()
    if h_val == h_val2:
      res = True
  return res
#
#
def download_package_hash(fname, path):
  try:
    info=get_pkg_info_from_yaml(fname)
    if not info: return None
    ffname=os.path.basename(info['filename'])
    if path:  ffname=path+"\\"+ffname  
    if check_md5_file(info['MD5sum'], ffname):
      return os.path.basename(info['filename'])
    return None
  except:
    return None

def download_package_file(fname, path=""):
  if not os.path.exists(path) : os.makedirs(path)
  fname=fname.split(',')[0]
  v=download_package_hash(fname, path)
  if v:
    return v

  file_name=os.path.basename(fname)
  url="%spkg_download.cgi?name=%s" % (PKG_REPO_BASE, fname)
  res=requests.get(url, stream=True)
  if res.status_code == 200:
    file_name, size = get_attached_filename(res, file_name, path)
    if check_md5_file(res.headers['Content-MD5sum'], file_name):
      return os.path.basename(file_name)
    #
    # save to file
    dl_chunk_size=1024
    save_download_file(res, file_name, size, dl_chunk_size)
    print("")
    return os.path.basename(file_name)
  else:
    print("Fail to download: %s" % fname)
    return None
#
#
def get_pkg_dep(name, typ='json'):
    url="%spkg_dep.cgi?name=%s&type=%s" % (PKG_REPO_BASE, name, typ)
    res=requests.get(url)
    if res.status_code == 200:
        lst=res.text
        return lst
    return None
#
#
def get_pkg_list(pname):
    url="%spkg_list.cgi?name=%s" % (PKG_REPO_BASE, pname)
    res=requests.get(url)
    if res.status_code == 200:
        lst=eval(res.text)
        return lst
    return []
#
#
def get_pkgs_yaml(pname):
  url="%sget_pkg_dep.cgi?name=%s" % (PKG_REPO_BASE, pname)
  res=requests.get(url)
  if res.status_code == 200:
    lst=res.text.split()
    return lst
  return []

#######
#
#
def is_meta_pkg(name):
  return (name in PKG_LIST) or (name in LIB_LIST)

def exist_meta_pkg(names):
  for n in names:
    if is_meta_pkg(n) : return True
  return False

def get_hash_value(fname):
  if os.path.exists(fname):
    return hashlib.md5(open(fname, 'rb').read()).hexdigest()
  else:
    return None

def get_pkg_name(fname):
  name=os.path.basename(fname)
  if PKG_PREFIX in name:
    return name.replace(PKG_PREFIX, "").replace(PKG_EXT, "").replace("-", "_")
  else:
    return name.replace(PKG_EXT, "")

def split_drive_letter(fname):
  x=re.match(r'^[a-zA-Z]:', fname)
  if x : 
    sp=x.span()
    return (fname[sp[0]:sp[1]], fname[sp[1]:])
  return ["", fname]

#
#
def default_pkgmgr_db(drv=None):
  if drv is None:
     drv=os.path.getcwd()[:2]
  return "%s%s/%s" % (drv, PKG_MGR_DIR, PKG_DB)

#
def remove_pkg_file_all(pkg, drv):
  dbname=default_pkgmgr_db(drv)
  files=select_install_info(pkg, dbname)

  if files:
    sfiles=sorted(files, key=len, reverse=True)
    cnt=0
    for f in sfiles:
      fname="%s%s" % (drv, f)
      if os.path.exists(fname):
        if os.path.isfile(fname):
          os.remove(fname)
        else:
          try:
            os.removedirs(fname)
          except:
            pass
      print("\rRemoving %s  " % getMonDots(cnt), end="", flush=True)
      cnt += 1
    delete_install_info(pkg, dbname)
    delete_pkg_data(pkg, dbname)
  print()
  return

#
#
def get_installed_pkgs(drv):
  dbname=default_pkgmgr_db(drv)
  if not os.path.exists(dbname) :
    print("No database:", dbname)
  return select_install_info_name(dbname)
  
####
# Download packages
#
def get_pkgs(names, path=""):
  for f in names:
    download_package_file(f, path)

#####
# Database
#

def get_dbname(to_dir, db):
  d, nm=split_drive_letter(to_dir)
  dbname = d+PKG_MGR_DIR+"/"+db
  return dbname

#
#  create table
def create_db_table(name, schema, dbname=PKG_DB):
  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    try:
      create_table = "create table %s (%s)" % (name, schema)
      c.execute(create_table)
      conn.commit()
    except:
      pass
    conn.close()

#
# exec SQL
def exec_sql(sql, dbname=PKG_DB):
  res=[]
  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    res=c.execute(sql).fetchall()
    conn.commit()
    conn.close()
  return res

#
#
def list_except(x, y, delim=":"):
  xx=x.split(delim)
  yy=y.split(delim)
  res=[]
  for v in xx:
    if not v in yy:
      res.append(v)
  return delim.join(res)

#
#
def pkgname_matching_pattern(name, exact=False):
  if exact :
    res="name='%s'" % name
  else:
    res="name='%s' or name glob '%s,*' or name glob '*,%s' or name glob '*,%s,*'" % (name, name, name, name)
  return res

######################
#  for table 'package'
#
def insert_pkg_data(name, fname, h_val=None, dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  create_db_table('packages', 'name text, fname text, run_dep text, lib_dep text, h_val text, uptime timestamp', dbname)

  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    sql="delete from packages where name='%s'" % name
    c.execute(sql)
    conn.commit()

    sql = "insert into packages (name, fname, h_val,run_dep,lib_dep,uptime) values (?,?,?,?,?,?)"
    ftime = datetime.datetime.fromtimestamp(os.stat(fname).st_mtime)
    res=get_pkg_dep(name).split("\n")
    h_val=get_hash_value(fname)

    data=(name, os.path.basename(fname), h_val, res[0], res[1], ftime)
    c.execute(sql, data)
    conn.commit()

    conn.close()
#
#
def select_pkg_data(name, dbname=None):
  res=[]
  if dbname is None: dbname=default_pkgmgr_db()
  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    if name == 'all':
      sql = "select * from packages"
    else:
      sql = "select * from packages where %s" % pkgname_matching_pattern(name)
    res=c.execute(sql).fetchall()
    conn.commit()
    conn.close()
  return res

#
#
def get_hash_valeu_from_db(name, dbname=None):
  res=[]
  if dbname is None: dbname=default_pkgmgr_db()
  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    sql = "select h_val from packages where %s" % pkgname_matching_pattern(name)
    res=c.execute(sql).fetchall()
    conn.commit()
    conn.close()
  return res[0]
#
#
def delete_pkg_data(name, dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  sql="delete from packages where %s" % pkgname_matching_pattern(name)
  try:
    res=exec_sql(sql, dbname)
    return True
  except:
    return False

#############################
#  for table 'install_info'
#
def insert_install_info(pkgname, fname, dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  create_db_table('install_info', "name text, path text, uptime timestamp", dbname)

  with closing(sqlite3.connect(dbname)) as conn:
    c = conn.cursor()
    sql = "insert into install_info (name, path, uptime) values (?,?,?)"
    ftime = datetime.datetime.now()
    data=(pkgname, fname, ftime)
    c.execute(sql, data)
    conn.commit()
    conn.close()

#
#
def select_install_info(name, dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  sql="select * from install_info where %s;" % pkgname_matching_pattern(name)
  try:
    res=exec_sql(sql, dbname)
    return [x[1] for x in res]
  except:
    return []

#
#
def delete_install_info(name, dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  sql="delete from install_info where %s;" % pkgname_matching_pattern(name)
  try:
    res=exec_sql(sql, dbname)
    return True
  except:
    return False
#
#
def select_install_info_name(dbname=None):
  if dbname is None: dbname=default_pkgmgr_db()
  sql="select distinct name from install_info;"
  try:
    res=exec_sql(sql, dbname)
    return [x[0] for x in res]
  except:
    return []

########################
# untar package file
# 
def untar(fname, to_dir, num=10, db=None):
  dbname=None
  signal.signal(signal.SIGINT, signal.SIG_DFL)
  try:
    arc=tarfile.open(fname)
    pkgname=file_to_pkgname(fname)
    if db:
      dbname=get_dbname(to_dir, db)
      if not os.path.exists(os.path.dirname(dbname)):
        os.makedirs(os.path.dirname(dbname))
      insert_pkg_data(pkgname, fname, None, dbname)

    members=arc.getnames()
    n=len(members)
    x=n/num
    if x == 0 : x=1
    bar = ">" + " " *num

    for i in range(n):
      try:
        arc.extract(members[i], path=to_dir)
        if db:
          insert_install_info(pkgname, to_dir[2:]+"\\"+members[i], dbname)
      except:
        print("===Fail to extract===", members[i])
          
      bar = "=" * int(i/x) + ">" + " " * int((n-i)/x)
      s="\rExtract: %s |%s|(%d%%) %s     " % (os.path.basename(fname), bar, int(i*100/n), getMonChar(i))
      print(s, end="")
    print ("\rExtracted:",fname, "==>", to_dir, " " *(num+10))
    arc.close()
  except:
    print(fname,": Fail to extract...              ")
    #traceback.print_exc()
    try:
      arc.close()
    except:
      pass

#
#
def check_pkg_installed(fname, to_pkgdir):
  try:
    name=file_to_pkgname(os.path.basename(fname))
    dbname=get_dbname(to_pkgdir, PKG_DB)
    data=select_pkg_data(name, dbname)
    if data :
      return check_md5_file(data[0][4], fname)
    else:
      return False
  except:
    return False
#
#
def file_to_pkgname(fname, pkgpath="__pkg__/pkgs.yaml"):
  data=load_yaml(pkgpath)
  ffname=os.path.basename(fname)
  for x in data:
    if ffname == os.path.basename( x['filename']) :  return x['package']
  print("Unknown pkg:", fname)
  return fname.replace(".tgz", "")

def pkgname_to_file(p, pkgpath="__pkg__/pkgs.yaml"):
  data=load_yaml(pkgpath)
  for x in data:
    pname=x['package'].split(',')
    if p in pname:  return os.path.basename(x['filename'])
  return None


#
def get_filename(name):
  lst=load_pkg_list()
  try:
    for x in lst:
      if name == lst[x]['package']:
        return lst[x]['filename']
  except:
    return None

#
#  install package file
def install_package(fname, dname, flag=False, verbose=False):
  to_libdir=dname+"\\local"
  to_optlibdir=dname+"\\opt\\local"
  to_pkgdir=dname+"\\opt"

  if not os.path.exists(to_libdir) :
    os.makedirs(to_libdir)
  if not os.path.exists(to_pkgdir) :
    os.makedirs(to_pkgdir)

  signal.signal(signal.SIGINT, signal.SIG_DFL)

  ff=file_to_pkgname(os.path.basename(fname))

  if PKG_PREFIX in fname:
    if flag or not check_pkg_installed(fname, to_pkgdir):
      untar(fname, to_pkgdir, 10, PKG_DB)
    else:
      if verbose:
        print("Skip install", ff)
  else:
    if "setup" in fname:
      if not os.path.exists(to_pkgdir+"\\start_ros.bat"):
        untar(fname, to_pkgdir)
    else:
      if flag or not check_pkg_installed(fname, to_pkgdir):
        if 'opt_local' in get_filename(ff):
          untar(fname, to_pkgdir, 10, PKG_DB)
        else: 
          untar(fname, to_libdir, 10, PKG_DB)
      else:
        if verbose :
          print("Skip install", ff)

#
# install all package files
def install_package_all(path, dname, flag=False, verbose=False):
  f_list=glob.glob(path+"/*.tgz")

  for fname in f_list:
    install_package(fname, dname, flag, verbose)

########################################
# Pkgs.yaml
#
def mkInfo(name, ver, fname, desc, license, maintainer, deps):
  data={"package" : name, 
        "version" : ver,
        "filename" : fname,
        "description" : desc,
        "license" : license,
        "maintainer" : maintainer,
        "buildtool" : "VS2015 x64",
        "MD5sum" : get_hash_value(fname),
        "depend" : deps
        }
  return data
#
#
def toXMLData(eles):
  res=""
  try:
    for ele in eles:
      res += ele.toxml()
  except:
    pass
  return res
#
#    
def getTextData(dom, tag, fname=""):
  try:
    ele=dom.getElementsByTagName(tag) 
    return ele[0].childNodes[0].data
  except:
    print( "ERROR in %s(%s)" % (tag, fname))
    return (toXMLData(ele[0].childNodes))
#
#
def getAttribute(dom, tag, attr):
  try:
    ele=dom.getElementsByTagName(tag) 
    return ele[0].getAttribute(attr)
  except:
    print( "ERROR in %s" % tag)
    return ""

######################################
#
# ROS package info
def get_pkg_info(lst):
  for v in lst:
    if 'package.xml' in v:
      return v
  return Non
#
#
def get_package_xml(fname):
  try:
    arc=tarfile.open(fname)
    lst = arc.getnames()
    info = arc.extractfile(get_pkg_info(lst)).read()
    arc.close()
    return info.decode('utf-8')
  except:
    return None
#
#
def get_package_dom(fname):
  try:
    pkg_dom=dom=xml.dom.minidom.parseString(get_package_xml(fname))
    return pkg_dom
  except:
    return None
#
#
def get_pkg_data(fname):
    if os.path.exists(fname) :
      dom=get_package_dom(fname)
      if dom:
        pname=getTextData(dom, 'name') 
        desc=getTextData(dom, 'description', fname) 
        license=getTextData(dom, 'license') 
        maintainer=getTextData(dom, 'maintainer') + "<"+getAttribute(dom, 'maintainer', 'email') +">"
        ver=getTextData(dom, 'version') 
        deps=get_depends(dom)
        data=mkInfo(pname, ver, fname, desc, license, maintainer, deps)
        return data
      else:
        pname=file_to_pkg_name(fname)
        desc=fname
        license=""
        maintainer=""
        ver=""
        deps=[]
        data=mkInfo(pname, ver, fname, desc, license, maintainer, deps)
        print("Warning in %s" % fname)
        return data
    else:
      print("ERROR in %s" % fname)
      return {}
#
#
def save_yaml(fname, data):
  with open(fname, "w") as f:
     f.write(yaml.dump(data))
     f.close()
#
#
def load_yaml(fname):
  data=[]
  with open(fname, "r") as f:
    try:
      data=yaml.load(f, Loader=yaml.FullLoader)
    except:
      data=yaml.load(f)

    f.close()
  return data

#
#
def load_pkg_list(path="__pkg__/pkgs.yaml"):
  data=load_yaml(path)
  res={}
  for x in data:
    pkgs=x['package'].split(',')
    for p in pkgs:
      res[p]=x
  return res

def load_pkg_hash(path="__pkg__/pkgs.yaml"):
  data=load_yaml(path)
  res={}
  for x in data:
    res[x['package']] = x['MD5sum']
  return res

def get_pkg_info_from_yaml(name, path="__pkg__/pkgs.yaml"):
  data=load_yaml(path)
  for v in data:
    names=v['package'].split(',')
    if name in names:
      return v
  
def get_depend(pname, deps, info):
  if pname in info:
    dep=info[pname]['depend']
    for x in dep:
      if not x in deps:
        deps.append(x)
        get_depend(x, deps, info)
    return deps
  else:
    return deps

def get_depends(pname):
  deps=[]
  info = load_pkg_list()
  get_depend(pname, deps, info)
  deps.append(pname)
  deps.sort()
  return deps, info

def get_dep_lib(pname):
  deps, info=get_depends(pname)
  pkg_list=list(info.keys())
  libs=[]
  pkgs=[]
  for x in deps:
    if x in pkg_list:
      pkgs.append(x)
    else:
      libs.append(x)
  return pkgs, libs

def get_depend_pkgs(name):
  info=load_pkg_list()
  res=[]
  for x in list(info.keys()):
    if name  in info[x]['depend']:
      res.append(x)
  return res

if __name__ == '__main__':
  fname=sys.argv[1]
  arc=tarfile.open(fname)
  lst=arc.getnames()
  pat=re.compile('package[\w]*\.xml')
  for v in lst:
    if pat.search(v):
      print(v)
  arc.close()
