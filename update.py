#!/usr/bin/python2.6

import sys
import os
import stat
import urllib2
from datetime import datetime
import re
import time
from subprocess import check_call
from tempfile import NamedTemporaryFile
from optparse import OptionParser

parser = OptionParser(usage="Usage: %prog [OPTIONS]")
parser.add_option('--download',
                  action="store_true",
                  dest='download',
                  default=False)
options, args = parser.parse_args()

file_mode = 0o644

sys.path.append('.')
from BeautifulSoup import BeautifulSoup

sys.path.append('PyRSS2Gen')
import PyRSS2Gen

download_directory = "downloaded"
check_call(["mkdir", "-p", download_directory])

podcast_title = "Tom Ravenscroft on BBC Radio 6"
podcast_description = "An unofficial podcast for Tom Ravenscroft's show on BBC Radio 6, which annoyingly is only available through iPlayer"
show_url = "http://www.bbc.co.uk/programmes/b00slvl3"
def episode_description(f):
    # Could examine the file's ID3 tags or extract the date
    # from the filename to make this more interesting
    return "An episode of Tom Ravenscroft's show on BBC Radio 6"

number_to_keep = None
base_podcast_url = None

try:
    if len(args) != 2:
        raise Exception, "Wrong number of arguments"
    number_to_keep = int(args[0])
    base_podcast_url = args[1]
except Exception as e:
    print >> sys.stderr, str(e)
    print >> sys.stderr, "Usage: %s <NUMBER-TO-KEEP> <BASE_PODCAST_URL>"
    sys.exit(1)

def is_mp3(f):
    return re.search('\.mp3$',f,re.I)

files = [ os.path.join(download_directory,x) for x in os.listdir(download_directory) if is_mp3(x) ]

def mtime(f):
    return datetime.fromtimestamp(os.stat(f)[stat.ST_MTIME])

files.sort( key = mtime )

for f in files[0:-number_to_keep]:
    os.remove(f)

opener = urllib2.build_opener()

soup = BeautifulSoup(opener.open(show_url))
if not soup:
    raise Exception, "Parsing "+show_url+" with BeautifulSoup failed"

def iplayer_console_tag(x):
    if x.name != 'a':
        return False
    for t in x.attrs:
        if t[0] == 'href':
            if re.search('^http://www.bbc.co.uk/iplayer/console/[a-z0-9]+$',t[1]):
                return True
    return False

a = soup.find( iplayer_console_tag )
if not a:
    raise Exception, "Couldn't find the iplayer console tag in "+show_url

check_call(["mkdir","-p",download_directory])

if options.download:
    check_call(["get_iplayer/get_iplayer", "--type=radio", "-o", download_directory])

wma_files = [os.path.join(download_directory,x) for x in os.listdir(download_directory) if x.endswith('.wma')]
wma_files.sort(key=mtime)
if wma_files:
    wma_output = wma_files[-1]

    try:
        tmp_file = NamedTemporaryFile(dir=download_directory, delete=False)
        check_call(["mplayer", "-quiet", "-vo", "null", "-vc", "dummy", "-ao", "pcm:waveheader:file="+tmp_file.name, wma_output])

        mp3_file_leafname = datetime.now().strftime("ravenscroft-%Y-%M-%d-%H:%m:%S.mp3")
        mp3_file = os.path.join(download_directory, mp3_file_leafname)

        check_call(["lame", "--quiet", "-V", "4", tmp_file.name, mp3_file])
        os.remove(wma_output)
    finally:
        os.remove(tmp_file.name)
else:
    print "Warning: no WMA file found to transcode, just regenerating podcast.xml"

# Now generate the XML for the podcast:

files = [ x for x in os.listdir(download_directory) if is_mp3(x) ]
files.sort( key = lambda x: mtime(os.path.join(download_directory,x)) )

# Make them readable:
for f in files:
    time.sleep(2)
    os.chmod(os.path.join(download_directory,f),file_mode)

def item_from_file(f):
    full = os.path.join(download_directory,f)
    extension_removed = re.sub('\.mp3$','',f,re.I)
    url_for_mp3 = base_podcast_url + urllib2.quote(f)
    return PyRSS2Gen.RSSItem(
        title = extension_removed,
        link = show_url,
        description = episode_description(f),
        guid = PyRSS2Gen.Guid(url_for_mp3),
        pubDate = mtime(full),
        enclosure = PyRSS2Gen.Enclosure(url_for_mp3,
                                        os.path.getsize(full),
                                        "audio/mpeg"))

rss = PyRSS2Gen.RSS2(
    title = podcast_title,
    link = show_url,
    description = podcast_description,
    lastBuildDate = datetime.now(),
    items = [ item_from_file(f) for f in files ] )

output_filename = os.path.join(download_directory,"podcast.xml")
rss.write_xml(open(output_filename,"w"))
os.chmod(output_filename,file_mode)
