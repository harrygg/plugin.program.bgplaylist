# -*- coding: utf-8 -*-
import os, xbmc, xbmcaddon, xbmcgui, requests, re, xbmcvfs
from resources.mapping import *
DEBUG = False

def log(msg, level = xbmc.LOGNOTICE):
  if c_debug or level == xbmc.LOGERROR:
    xbmc.log('%s | %s' % (id, msg), level)
  if level == xbmc.LOGERROR:
    import traceback
    xbmc.log('%s | %s' % (id, traceback.format_exc()), xbmc.LOGERROR)

def notify_error(msg):
  log(msg, xbmc.LOGERROR)
  xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % ('Грешка!', msg, '10000', ''))  
  
def show_progress(percent, msg):
  if c_debug or is_manual_run:
    heading = name.encode('utf-8') + ' ' + str(percent) + '%'
    dp.update(percent, heading, str(msg))
    log(msg)

def get_response_size(r):
  try: 
    size = int(r.headers['Content-length'])
    log ("Content-length: %s " % size)
    return size
  except KeyError:
    try: 
      size = len(r.content)
      log ("len(r.content): %s " % size)
      return size
    except: 
      return -1
      
#implementation of iter_lines to include progress bar
def iter_lines(r, chunk_size, delimiter = None):
  global progress
  pending = None
  i = 0
  for chunk in r.iter_content(chunk_size=chunk_size, decode_unicode=True):
    if i >= chunk_size:
      progress += 1 
      show_progress(progress, 'Parsing server response')
    i += chunk_size
    if DEBUG:
      xbmc.sleep(50) 
    if pending is not None:
      chunk = pending + chunk
    if delimiter:
      lines = chunk.split(delimiter)
    else:
      lines = chunk.splitlines()
    if lines and lines[-1] and chunk and lines[-1][-1] == chunk[-1]:
      pending = lines.pop()
    else:
      pending = None
    for line in lines:
      yield line
      
  if pending is not None:
      yield pending

def get_playlist():
  lines = []
  global progress, source_m3u
  progress_max = 70
  progress += 1
  show_progress(progress, 'Getting playlist from %s ' % m3u_file)
  if is_pl_remote:
    lines = get_playlist_from_url(progress_max)
  else:
    lines = get_playlist_from_file(progress_max)
  log("get_playlist: %s lines" % len(lines))
  progress = progress_max
  source_m3u = ''.join(lines)
  return lines
  
def get_playlist_from_url(progress_max):
  lines = []
  try:
    v = xbmc.getInfoLabel("System.BuildVersion" )
    r = requests.get(m3u_file, headers={"User-agent": "Kodi %s" % v}, stream=True)
    size = get_response_size(r)
    if size > 0:
      chunk_size = size / progress_max
    else: 
      chunk_size = 1024
    
    #using r.text.splitlines() is way too slow on singleboard devices!!!
    for line in iter_lines(r, chunk_size):
      lines.append(line)
    
    #raise Exception('Test exception thrown!')
    return lines
  except Exception, er:
    log(er, xbmc.LOGERROR)
  return lines
  
def file_iter_lines(f, chunk_size=1024):
  global progress
  pending = None
  i = 0 
  while True:
    if DEBUG:
      xbmc.sleep(50) 
    if i >= chunk_size:
      progress += 1 
      show_progress(progress, 'Parsing file content')
    i += chunk_size 
    try: chunk = os.read(f.fileno(), chunk_size)
    except: chunk = False
    
    if not chunk:
      break
    if pending is not None:
      chunk = pending + chunk
      pending = None
    lines = chunk.splitlines()
    if lines and lines[-1]:
      pending = lines.pop()
    for line in lines:
      yield line
  if pending:
    yield(pending)

        
def get_playlist_from_file(progress_max):
  lines = []
  try:
    if os.path.isfile(m3u_file):
      size = os.path.getsize(m3u_file)
      progress_step = size / progress_max
      
      with open(m3u_file) as f: 
        #using readlines() too slow
        for line in file_iter_lines(f, progress_step):
          lines.append(line)

  except Exception, er:
    log(er, xbmc.LOGERROR)
  return lines

def parse_playlist(lines):
  channels = {}
  exported_names = ''
  try:
    global progress
    n_lines = len(lines)
    #log("parse_playlist parsing %s rows" % n_lines)
    progress_step = n_lines / 15
    n = 0
    
    for i in range(0, n_lines):
      if lines[i].startswith("#EXTINF"):
        name = re.compile(',\d*\.*\s*(.*)').findall(lines[i])[0]
        
        exported_names += name + '\n'
          
        #try: log("Извлечен канал: %s" % name.encode('utf-8'))
        ##except UnicodeDecodeError:
        #  try: log(name)
        #  except: pass
        
        i += 1
        channels[name] = lines[i]

        n += 1
        if i % progress_step == 0:
          progress += 1
          show_progress(progress,'Извличане на канали от плейлиста')

    if n == 0:
      log("Extracted 0 channels from m3u content: \n%s" % source_m3u)
    if export_names:
      with open(names_file, 'w') as n:
        n.write(exported_names)
      
  except Exception, er:
    log(er, xbmc.LOGERROR)
  return channels

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

def load_channel_order():
  channels = []
  try:
    if os.path.isfile(order_file):
      with open(order_file) as f:
        for l in f:
          channels.append(l.rstrip())
    else:
      notify_error('Липсващ шаблон с подредба на канали')
  except Exception, er:
    log(er, xbmc.LOGERROR)
  return channels
    
def write_playlist():
  try:
    res = False
    global progress
    with open(new_m3u, 'w') as w:
      ordered_channels = load_channel_order()
      n_order = len(ordered_channels)
      if n_order != 0 and sorting:   
        progress_step = n_order / 10
        ### Sort channels and write playlist  
        n = 1
        w.write('#EXTM3U\n')
        for i in range(0, n_order):
          c_name = ordered_channels[i]
          try: id = channels_map[c_name]['id']
          except: id = c_name
          try: group = channels_map[c_name]['group']
          except: group = ''
          try: logo = channels_map[c_name]['logo']
          except: logo = ''
          #log("Добавяне на сортиран канал: %s. %s" % (n, c_name))
          
          line = EXTINF % (id,group,logo,c_name)
          try :
            url = channels[c_name]
            w.write(line)
            w.write(url + "\n")
            del channels[c_name]
            n += 1
            if i % progress_step == 0:
              show_progress(progress, 'Добавяне на канал')
              progress += 1
          except KeyError:
            log('Не е намерен мапинг за канал %s ' % c_name)
          except Exception, er:
            log(er, xbmc.LOGERROR)
        show_progress(96,'%s канала бяха пренаредени' % n)
        ###################################################
        ### Add missing channels if option is True
        ###################################################
        log('Останали несортирани канали в плейлистата: %s' % len(channels))
        if add_missing:
          log('Добавянето на несортираните канали е разрешено')
          for name,url in channels.items():
            try: id = channels_map[name]['id']
            except: id = name
            try: group = channels_map[name]['group']
            except: group = ''
            try: logo = channels_map[name]['logo']
            except: logo = ''
            line = EXTINF % (id,group,logo,name)
            w.write(line)
            w.write(url + "\n")
        show_progress(97,'Плейлиста беше успешно записана')
      else: 
        ### Do not sort channels
        show_progress(97,'Плейлиста не беше пренаредена!')
        w.write(source_m3u)
  except Exception, er:
    log(er, xbmc.LOGERROR)

###################################################
### Settings and variables 
###################################################
addon = xbmcaddon.Addon()
id = addon.getAddonInfo('id')
name = addon.getAddonInfo('name').decode('utf-8')
profile_dir = xbmc.translatePath( addon.getAddonInfo('profile') ).decode('utf-8')
cwd = xbmc.translatePath( addon.getAddonInfo('path') ).decode('utf-8')
c_debug = True if addon.getSetting('debug') == 'true' else False
add_missing = True if addon.getSetting('add_missing') == 'true' else False
export_names = True if addon.getSetting('export_names') == 'true' else False
if export_names:
  export_to_folder = addon.getSetting('export_to_folder')
  if os.path.isdir(export_to_folder):
    names_file = os.path.join(export_to_folder, 'names.txt')
  else:
    names_file = os.path.join(profile_dir, 'names.txt')

order_file = addon.getSetting('order_file')
if not os.path.isfile(order_file):
  order_file = os.path.join(cwd, 'resources', 'order.txt')
log('order file: %s' % order_file)

sorting = True
EXTINF = '#EXTINF:-1 tvg-id="%s" group-title="%s" tvg-logo="%s",%s\n'
log('sorting: %s' % sorting)
pl_name = 'bgpl.m3u'
source_m3u = ''
new_m3u = os.path.join(profile_dir, pl_name)
log('Playlist path: %s' % new_m3u)
progress = 0

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
### Get playlist from source (server or file) and parse it (sort channels)
###################################################
try:
  is_pl_remote = addon.getSetting('m3u_path_type') == '1'
  m3u_file = addon.getSetting('m3u_url') if is_pl_remote else addon.getSetting('m3u_path')
  log("source m3u file: " + m3u_file)

  if m3u_file.strip() == '':
    notify_error('Липсващ УРЛ за входяща плейлиста')
  else:
    lines = get_playlist()
    channels = parse_playlist(lines)
    if len(channels) == 0:
      notify_error('Плейлистата не съдържа канали')
    else:
      write_playlist()

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
        log(er, xbmc.LOGERROR)
        notify_error('Плейлистата НЕ беше копирана!')

except Exception, er:
  log(er, xbmc.LOGERROR)

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