# -*- coding: utf-8 -*-
import os, xbmc, xbmcaddon, xbmcgui, requests, re, xbmcvfs

def log(msg, level = xbmc.LOGNOTICE):
  if c_debug or level == 4:
    xbmc.log('%s | %s' % (id, msg), level)

def notify_error(msg):
  log(msg, 4)
  xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % ('Грешка!', msg, '10000', ''))  
  
def show_progress(percent, msg):
  if c_debug or is_manual_run:
    heading = name.encode('utf-8') + ' ' + str(percent) + '%'
    dp.update(percent, heading, str(msg))
    log(msg)

def get_playlist():
  if is_pl_remote:
    return get_playlist_from_url()
  else:
    return get_playlist_from_file()
  
def get_playlist_from_url():
  try:
    global old_m3u
    s = requests.Session()
    show_progress(1, 'Сваляне на плейлиста от %s ' % m3u_file)
    v = xbmc.getInfoLabel("System.BuildVersion" )
    r = s.get(m3u_file, headers={"User-agent": "Kodi %s" % v})
    old_m3u = r.text
    return r.text.splitlines()
  except Exception, er:
    log(er, 4)
    return []

def get_playlist_from_file():
  try:
    global old_m3u
    if os.path.isfile(m3u_file):
      with open(m3u_file) as f:
        old_m3u = f.readlines()
        return f.readlines()
    return r.text.splitlines()
  except Exception, er:
    log(er, 4)
    return []  

def parse_playlist(lines):
  channels = {}
  try:
    progress = 5
    n_lines = len(lines)
    step = n_lines / 50

    for i in range(0, n_lines):
      if lines[i].startswith("#EXTINF"):
        name = re.compile(',\d*\.*\s*(.*)').findall(lines[i])[0]
        log("Извлечен канал: %s" % name.encode('utf-8'))
        i += 1
        channels[name] = lines[i]
        if i % step == 0:
          progress += 1
          show_progress(progress,'Извличане на канали от плейлиста')

    show_progress(progress + 1,'Извлечени %s канала' % len(channels))
  except Exception, er:
    log(er, 4)
  return channels

def get_map():
  map = []
  try:
    with open(mp) as f:
      map = f.readlines()
  except Exception, er:
    log(er, 4)  
  return map

def channel_disabled(map):
  return (map.startswith('\t') or map.startswith(' ') or map.startswith('#') or map.startswith('\r') or map.startswith('\n'))
    
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

def write_playlist(map):
  res = False
  with open(new_m3u, 'w') as w:
    if len(map) != 0 and sorting:   
      ### Sort channels and write playlist  
      n = 0
      w.write('#EXTM3U\n')
      for m in map:
        if not channel_disabled(m): 
          name,id,group,logo = m.split(',')
          log("Добавяне на сортиран канал: %s" % name)
          line = '#EXTINF:-1 tvg-id="%s" group-name="%s" tvg-logo="%s",%s\n' % (id,group,logo.rstrip(),name)
          try :
            url = channels[name.decode('utf-8')]
            w.write(line)
            w.write(url + "\n")
            n += 1
            raise KeyError
          except KeyError:
            log('Не е намерен мапинг за канал %s ' % name)
          except Exception, er:
            log(er, 4)         
      show_progress(96,'%s канала бяха пренаредени' % n)
      show_progress(97,'Плейлиста беше успешно записана')
    else: 
      ### Do not sort channels
      show_progress(97,'Плейлиста не беше пренаредена!')
      w.write(old_m3u)
    
  res = True
  return res

###################################################
### Settings and variables 
###################################################
addon = xbmcaddon.Addon()
id = addon.getAddonInfo('id')
name = addon.getAddonInfo('name').decode('utf-8')
profile_dir = xbmc.translatePath( addon.getAddonInfo('profile') ).decode('utf-8')
cwd = xbmc.translatePath( addon.getAddonInfo('path') ).decode('utf-8')
c_debug = True if addon.getSetting('debug') == 'true' else False
mp = addon.getSetting('mapping_file')
if not os.path.isfile(mp):
  mp = os.path.join(cwd, 'resources', 'mapping-tvbg.txt')
log('mapping_file: %s' % mp)
sorting = True
log('sorting: %s' % sorting)
pl_name = 'bgpl.m3u'
old_m3u = ''
new_m3u = os.path.join(profile_dir, pl_name)
log('Playlist path: %s' % new_m3u)

if addon.getSetting('firstrun') == 'true':
  addon.setSetting('firstrun', 'false')
  addon.openSettings()
  
###################################################
### If addon is run manually display progress dialog
###################################################
is_manual_run = False if len(sys.argv) > 1 and sys.argv[1] == 'False' else True
if not is_manual_run:
  log('Автоматично генериране на плейлиста')
dp = False
update('operation', 'regeneration')
if is_manual_run or c_debug:
  dp = xbmcgui.DialogProgressBG()
  dp.create(heading = name)

###################################################
### Get playlist from source (server or file) and parse (sort channels) it
###################################################
is_pl_remote = addon.getSetting('m3u_path_type') == '1'
m3u_file = addon.getSetting('m3u_url') if is_pl_remote else addon.getSetting('m3u_path')
log("m3u_file: " + m3u_file)
if m3u_file.strip() == '':
  notify_error('Липсващ УРЛ за входна плейлиста')
else:
  lines = get_playlist()
  if len(lines) == 0:
    notify_error('Плейлистата не съдържа канали')
  else:
    channels = parse_playlist(lines)
    map = get_map()
    write_playlist(map)

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
      notify_error('Плейлистата НЕ беше копирана!')
    
    ####################################################
    ### Set next run
    ####################################################
    roi = int(addon.getSetting('run_on_interval')) * 60
    show_progress(99,'Настройване на AlarmClock. Следващото изпълнение е след %s часа' % (roi / 60))
    xbmc.executebuiltin('AlarmClock(%s, RunScript(%s, False), %s, silent)' % (id, id, roi))
     
    ####################################################
    ###Restart PVR Sertice to reload channels' streams
    ####################################################
    if addon.getSetting('reload_pvr') == 'true':
      xbmc.executebuiltin('XBMC.StopPVRManager')
      xbmc.executebuiltin('XBMC.StartPVRManager')

if dp:
  dp.close()