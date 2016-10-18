# -*- coding: utf-8 -*-
import os, xbmc, xbmcaddon, xbmcgui, requests, re, xbmcvfs

def log(msg, level = xbmc.LOGNOTICE):
  if c_debug or level == 4:
    xbmc.log('%s | %s' % (id, msg), level)

def show_progress(percent, msg):
  if c_debug or is_manual_run:
    heading = name.encode('utf-8') + ' ' + str(percent) + '%'
    dp.update(percent, heading, str(msg))
    log(msg)

def close_progress():
  if c_debug or is_manual_run:
    dp.close()

def update(action, location, crash=None):
  try:
    from ga import ga
    p = {}
    p['an'] = addon.getAddonInfo('name')
    p['av'] = addon.getAddonInfo('version')
    p['ec'] = 'Addon actions'
    p['ea'] = action
    p['ev'] = '1'
    p['ul'] = xbmc.getLanguage()
    p['cd'] = location
    ga('UA-79422131-10').update(p, crash)
  except Exception, er:
    log(er)
  
###################################################
### Settings
###################################################
is_manual_run = False if len(sys.argv) > 1 and sys.argv[1] == 'False' else True
if not is_manual_run:
  xbmc.log('%s | Автоматично генериране на плейлиста' % id)
addon = xbmcaddon.Addon()
id = addon.getAddonInfo('id')
name = addon.getAddonInfo('name').decode('utf-8')
profile_dir = xbmc.translatePath( addon.getAddonInfo('profile') ).decode('utf-8')
cwd = xbmc.translatePath( addon.getAddonInfo('path') ).decode('utf-8')
c_debug = True if addon.getSetting('debug') == 'true' else False
s = requests.Session()
url = addon.getSetting('m3u_url')
r = None
channels = {}
pl_name = 'bgpl.m3u'

if addon.getSetting('firstrun') == 'true':
  addon.setSetting('firstrun', 'false')
  addon.openSettings()
  
###################################################
### Addon logic
###################################################
if c_debug or is_manual_run:
  dp = xbmcgui.DialogProgressBG()
  dp.create(heading = name)

###################################################
### Get playlist from server and parse it
###################################################
show_progress(1, 'Сваляне на плейлиста от %s ' % url)
update('operation', 'regeneration')
r = s.get(url, headers={"User-agent": "Kodi"})
lines = r.text.splitlines()

progress = 5
n_lines = len(lines)
step = n_lines / 50

for i in range(0, n_lines):
  if lines[i].startswith("#EXTINF"):
    name = re.compile(',\d*\.*\s*(.*)').findall(lines[i])[0]
    log("Extracted channel name: %s" % name.encode('utf-8'))
    i += 1
    channels[name] = lines[i]
    if i % step == 0:
      progress += 1
      show_progress(progress,'Извличане на канали от плейлиста')

show_progress(progress + 1,'Извлечени %s канала' % len(channels))

###################################################
### Parsing mapping file, writing playlist
###################################################
mp = addon.getSetting('mapping_file')
if not os.path.isfile(mp):
  mp = os.path.join(cwd, 'resources', 'mapping-tvbg.txt')
log('mapping_file: %s' % mp)
new_m3u = os.path.join(profile_dir, pl_name)
log('Playlist path: %s' % new_m3u)

###################################################
### Sort channels and write playlist
###################################################
n = 0
with open(mp) as f, open(new_m3u, 'w') as w:
  w.write('#EXTM3U\n')
  lines = f.readlines()
  for l in lines:
    if not (l.startswith('\t') or l.startswith(' ') or l.startswith('#') or l.startswith('\r') or l.startswith('\n')): 
      s = l.split(',')
      log("Adding channel: " + s[0])
      line = '#EXTINF:-1 tvg-id="%s" group-name="%s" tvg-logo="%s",%s\n' % (s[1],s[2],s[3].rstrip(),s[0])
      w.write(line)
      url = channels[s[0].decode('utf-8')]
      w.write(url + "\n")
      n += 1
      
show_progress(96,'%s канала бяха пренаредени' % n)
show_progress(97,'Плейлиста беше успешно записана')

###################################################
### Copy playlist to additional folder if specified
###################################################
try:
  ctf = addon.getSetting('copy_to_folder')
  if addon.getSetting('copy_playlist') == 'true' and os.path.isdir(ctf):
    log('Copying playlist to: %s' % ctf)
    xbmcvfs.copy(new_m3u, os.path.join(ctf, pl_name))
    show_progress(98, 'Плейлиста беше успешно копирана')
except Exception, er:
  log(er, 4)
  xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % ("Error!", str(er), '10000', ''))
    
####################################################
### Set next run
####################################################
#show_progress(98,'Генерирането на плейлистата завърши!')
roi = int(addon.getSetting('run_on_interval')) * 60
show_progress(99,'Настройване на AlarmClock. Следващото изпълнение на скрипта ще бъде след %s часа' % (roi / 60))
xbmc.executebuiltin('AlarmClock(%s, RunScript(%s, False), %s, silent)' % (id, id, roi))
 
####################################################
###Restart PVR Sertice to reload channels' streams
####################################################
if addon.getSetting('reload_pvr') == 'true':
  xbmc.executebuiltin('XBMC.StopPVRManager')
  xbmc.executebuiltin('XBMC.StartPVRManager')

close_progress()