#!/usr/bin/env python
# -*- encoding: utf-8 -*-

#
# Copyright P. Christeas <p_christ@hol.gr> 2008-2010
#
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################
#
# Convert an OpenERP module to RPM package

import imp
import sys
import os
import glob
import subprocess
import re

from optparse import OptionParser

parser = OptionParser()
parser.add_option("-q", "--quiet",
                  action="store_false", dest="verbose", default=True,
                  help="don't print status messages to stdout")

parser.add_option("-r", "--onlyver",
                  action="store_true", dest="onlyver", default=False,
                  help="Generates the version string and exits.")

parser.add_option("-R", "--onlyrel",
                  action="store_true", dest="onlyrel", default=False,
                  help="Generates the release string and exits.")

parser.add_option("-g", "--gitver",
                  dest="gitver",
                  help="Reads the version information from file",
                  metavar = "GITVER_FILE")

parser.add_option("-C", "--rclass", dest="rclass",
                  help="use RCLASS release class", metavar="RCLASS")

parser.add_option("-x", "--exclude-from",
                  dest="exclude",
                  help="Reads the file FROM_LIST and excludes those modules",
                  metavar = "FROM_LIST")


parser.add_option("-n", "--name",
                  dest="name",
                  help="The name of the base package (openerp-addons)",
                  metavar = "NAME")
parser.add_option("--skip-unnamed", dest="skip_unnamed", action="store_true", default=False,
                  help="Relax checks and tolerate name errors, skipping addons")

(options, args) = parser.parse_args()

class release:
	version = '4.3.x'
	release = '1'
	def __init__(self, gitver=None):
		#sys.stderr.write("Init\n")
		self.version = ''
		self.subver = ''
		self.release = ''
		self.extraver = None
		self.mainver = ''
		if gitver:
		    try:
		        f = open(gitver, 'rb')
		        for line in f:
			    if not ':' in line:
				continue
			    key, val = line.split(':',1)
			    val = val.strip()
			    if key == 'Version':
				self.version = val
			    elif key == 'Release':
				self.release = val
			    elif key == 'Extra':
				self.extraver = val
			f.close()
			sys.stderr.write("Got version from file: v: %s (%s) , r: %s \n" %(self.version,self.subver,self.release))
		    except:
			sys.stderr.write("Get release exception: %s \n " % str(sys.exc_info()))
		else:
		    try:
			p = subprocess.Popen(["git", "describe", "--tags"], bufsize=4096, \
				stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
			(child_stdout, child_stdin) = (p.stdout, p.stdin)
			rescode = p.wait()
			if rescode != 0 : raise CalledProcessError, rescode
			res= child_stdout.read()
			#sys.stderr.write("Git version: %s\n" % res)
			resc = res.split('-')
			if re.match('g.*',resc[len(resc)-1]) :
				resc.pop()
			if len(resc)>1 :
				self.release = resc.pop().strip()
			else:
				self.release = '0'
			self.version = resc[0].lstrip('v')
			if self.version:
			    ma = re.match(r'([0-9\.]+)([a-z][\w]+)?',
					self.version)
			    if ma:
				self.version = ma.group(1)
				self.extraver = ma.group(2)

			self.subver ="-".join(resc[1:])
			sys.stderr.write("Got version from git: v: %s (%s) , r: %s \n" %(self.version,self.subver,self.release))
		    except:
			sys.stderr.write("Get release exception: %s \n " % str(sys.exc_info()))
		
		self.mainver = '.'.join(self.version.split('.')[:2])
		self.extrarel = ''
		if self.extraver:
		    self.extrarel += '0.'+ self.extraver + '.'
		self.extrarel += self.release
		

rel = release(options.gitver)

release_class = options.rclass or 'pub'
oname = options.name or 'openerp-addons'

knight = """
%%{?!pyver: %%define pyver %%(python -c 'import sys;print(sys.version[0:3])')}
%%{!?python_sitelib: %%define python_sitelib %%(%%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%%define release_class %s

Name:	%s
Version:	%s
Release:	%%mkrel %s
License:	AGPLv3
Group:		Databases
Summary:	Addons for OpenERP
#Source0:	%%{name}-%%{version}.tar.gz
URL:		http://www.openerp.com
BuildRoot:	%%{_tmppath}/%%{name}-%%{version}-%%{release}
BuildArch:	noarch

%%description
Addon modules for OpenERP

%%prep
cd %%{name}-%%{version}
# setup -q

%%build
cd %%{name}-%%{version}

""" % ( release_class,oname, rel.mainver+rel.subver,rel.extrarel)

inst_str = """
%install
cd %{name}-%{version}
rm -rf $RPM_BUILD_ROOT

install -d $RPM_BUILD_ROOT/%{python_sitelib}/openerp-server/addons
cp -ar ./* $RPM_BUILD_ROOT/%{python_sitelib}/openerp-server/addons/
"""

def get_module_info(name):
	try:
		mpath = os.path.join(name, '__openerp__.py')
		if not os.path.exists(mpath):
		    mpath = os.path.join(name, '__terp__.py')
		f = open(mpath, "r")
		data = f.read()
		info = eval(data)
		if 'version' in info:
			info['version'] = rel.mainver + '.' + info['version']+rel.subver
		f.close()
	except IOError:
		sys.stderr.write("Dir at %s may not be an OpenERP module.\n" % name)
		return {}
	except:
		sys.stderr.write(str( sys.exc_info()))
		return {}
	return info

def get_depends(deps,allnames):
	ret = []
	for dep in deps:
		if dep == "base" : continue
		if dep in allnames:
			ret.append(oname+"-"+dep)
		else:
			ret.append('openerp-addons-'+dep)
	ret = set(ret)
	if not ret : return ""
	return "Requires: %s \n" % (", ".join(ret))

# Write down dependencies for non-openerp python modules
# The format can either be a string, or a tuple, with the version required
def get_ext_depends(deps):
	ret = []
	ret_ver = []
	str_ret = ''
	for dep in deps:
		if type(dep) == type(tuple()):
			ret_ver.append(dep[0]+' '+ dep[1] + ' ' + dep[2])
		else:
			ret.append(dep)
	ret = set(ret)
	ret_ver = set(ret_ver)
	if ret:
		str_ret += "Requires: %s \n" % (", ".join(ret))
	if ret_ver:
		str_ret += "".join(map(lambda a: "Requires: %s\n" % a, ret_ver))
	return str_ret

def fmt_spec(name,info,allnames):
	""" Format the info object fields into a SPEC submodule section
	    allnames is a list with all supplied names
	"""
	if ('name' not in info) : return ""
	if options.skip_unnamed and not info['name']:
	    return ""
	if ('installable' in info) and not info['installable']:
	    return ""
	nii = "\n"
	nii += '%%package %s\n' % name;
	if 'version' in info:
		nii+= "Version: %s\n" % info['version']
	if not info['name']:
	    raise Exception("Addon %s should specify a name for summary!" % name)
	nii += """Group: Databases
Summary: %s
Requires: openerp-server >= %s
""" % (info['name'], rel.version.rsplit('.', 1)[0])
	if 'depends' in info:
		nii += get_depends(info['depends'],allnames)
	if 'ext_depends' in info:
		nii += get_ext_depends(info['ext_depends'])
	if 'author' in info:
		nii+= "Vendor: %s\n" % info['author']
	if 'website' in info  and info['website'] != '' :
		# we can only have one of the urls provided.
		ws = info['website']
		if ',' in ws:
		    ws = ws.split(', ')[0].strip()
		if '- ' in ws:
		    ws = ws.split('- ')[0].strip()
		nii+= "URL: %s\n" % ws
	if 'description' in info:
		nii += "\n%%description %s\n%s\n" % (name, info['description'])
	else:
		nii += "\n%%description %s\n%s\n" % (name, info['name'])
	nii +="""
%%files %s
%%defattr(-,root,root)
%%{python_sitelib}/openerp-server/addons/%s
""" % (name, name)
	return nii


info_dirs = []
no_dirs = []

if ( options.onlyver):
	print rel.mainver+rel.subver
	exit(0)

if ( options.onlyrel):
	print rel.extrarel
	exit(0)

exclude_modules = []
if options.exclude and len(options.exclude):
    f = open(options.exclude,'r')
    mods = f.readlines()
    for mname in mods:
        mname = mname.strip()
        if not mname:
            continue
        exclude_modules.append(mname)
    f.close()

for tdir in args:
        bdir = os.path.basename(tdir)
        if bdir in exclude_modules:
            no_dirs.append(bdir)
            continue
	info = get_module_info(tdir)
	if (not info ) or (not info.get('installable',True)) :
		no_dirs.append(bdir)
	else :
		info_dirs.append({'dir': bdir, 'info': info})


print knight
print inst_str

if no_dirs != [] :
	print 'pushd $RPM_BUILD_ROOT/%{python_sitelib}/openerp-server/addons/'
	for tdir in no_dirs:
		print "\trm -rf %s" % tdir
	print "popd\n"

allnames = set(map(lambda i: i['dir'], info_dirs))

for tinf in info_dirs:
	print fmt_spec(tinf['dir'],tinf['info'],allnames)

sys.stderr.write("Modules created: %d\n"% len(info_dirs))
#sys.stderr.write("Don't forget to create the archive, with:\n" \
	#"git archive --format=tar --prefix=openerp-addons-%s/ HEAD | gzip -c > openerp-addons-%s.tar.gz\n" \
	#% (rel.version.rsplit('.', 1)[0],rel.version.rsplit('.', 1)[0]));
#eof
