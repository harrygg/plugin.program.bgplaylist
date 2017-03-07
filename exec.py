# -*- coding: utf-8 -*-
import os 
import xbmc
import xbmcaddon
import xbmcgui
import requests
import re
import xbmcvfs
import json
import sqlite3
from resources.mapping import *

DEBUG = False

def log(msg, level = xbmc.LOGNOTICE):
  if c_debug or level == xbmc.LOGERROR:
    xbmc.log('%s | %s' % (addon_id, msg), level)
  if level == xbmc.LOGERROR:
    import traceback
    xbmc.log('%s | %s' % (addon_id, traceback.format_exc()), xbmc.LOGERROR)

def notify_error(msg):
  log(msg, xbmc.LOGERROR)
  xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % ('Грешка!', msg, '10000', ''))  
  
def show_progress(percent, msg):
  if c_debug or is_manual_run:
    heading = addon_name.encode('utf-8') + ' ' + str(percent) + '%'
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
  show_progress(progress, 'Използване на плейлиста от %s ' % m3u_file)
  if is_pl_remote:
    lines = get_playlist_from_url(progress_max)
  else:
    lines = get_playlist_from_file(progress_max)
  log("get_playlist: съдържа %s реда" % len(lines))
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

def get_channel_info_from_map(name, attr, default = ""):
  try: 
    ret = channels_map[name][attr]
    if ret == "": 
      ret = default
  except: ret = default
  return ret
  
def parse_playlist(lines):
  channels = {}
  exported_names = ''
  try:
    global progress, raw_radio_streams
    n_lines = len(lines)
    #log("parse_playlist parsing %s rows" % n_lines)
    progress_step = n_lines / 15
    n = 0
    
    for i in range(0, n_lines):
      if lines[i].startswith("#EXTINF"):
        name = re.compile(',\s*(.*)').findall(lines[i])[0]
        exported_names += name + '\n'
        is_radio = "radio=\"True" in lines[i]
        if is_radio:
          logo = get_channel_info_from_map(name, 'logo')
          #'#EXTINF:-1 radio="True" group-title="Радио" tvg-logo="%s",%s\n'
          raw_radio_streams += EXTINF % (True, "", "Радио", logo, name)
          raw_radio_streams += lines[i + 1] + '\n'
          i += 2
        else:       
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
    p['an'] = addon_name
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
          id = get_channel_info_from_map(c_name, 'id', c_name)
          group = get_channel_info_from_map(c_name, 'group', "Други")
          logo = get_channel_info_from_map(c_name, 'logo')
          #log("Добавяне на сортиран канал: %s. %s" % (n, c_name))
          
          line = EXTINF % (False, id, group, logo, c_name)
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
          for c_name, url in channels.items():
            if hide_lq_channels and "LQ" in c_name:
              continue
            id = get_channel_info_from_map(c_name, 'id', c_name)
            logo = get_channel_info_from_map(c_name, 'logo')
            group = get_channel_info_from_map(c_name, 'group', "Други")
            if group not in hidden_groups:
              line = EXTINF % (False, id, group, logo, c_name)
              w.write(line)
              w.write(url + "\n")
        
        ###################################################
        ### Add radio channels if such are found during the playlist parsing
        ###################################################       
        if raw_radio_streams != "":
          w.write(raw_radio_streams)
          
        show_progress(97,'Плейлиста беше успешно записана')
      else: 
        ### Do not sort channels
        show_progress(97,'Плейлиста не беше пренаредена!')
        w.write(source_m3u)
  except Exception, er:
    log(er, xbmc.LOGERROR)

def is_player_active():
  try:
    return xbmc.getCondVisibility("Pvr.IsPlayingTv") or xbmc.getCondVisibility("Pvr.IsPlayingRadio")
  except:
    return False

def delete_tvdb():
  db_file = os.path.join(db_dir, "TV29.db")
  if os.path.isfile(db_file):
    log("Trying to manually reset TV DB before restart %s" % db_file)
    conn = sqlite3.connect(db_file)
    with conn:
      cursor = conn.cursor()
      conn.execute('''DELETE FROM channels;''')
      log('''Executing query: "DELETE FROM channels;"''')
      conn.execute('''DELETE FROM map_channelgroups_channels;''')
      log('''Executing query: "DELETE FROM map_channelgroups_channels;"''')
      conn.execute('''DELETE FROM channelgroups;''')
      log('''Executing query: "DELETE FROM channelgroups;"''')
      conn.execute('''VACUUM;''')
      log('''Executing query: "VACUUM;"''')
      conn.commit()
  else:
    log("DB file does nto exist! %s" % db_file)
    

def delete_epgdb():
  db_file = os.path.join(db_dir, "Epg11.db")
  if os.path.isfile(db_file):
    log("Trying to reset EPG DB before restart %s" % db_file)
    conn = sqlite3.connect(db_file)
    with conn:
      cursor = conn.cursor()
      conn.execute('''DELETE FROM epg;''')
      log('''Executing query: "DELETE FROM epg;"''')
      conn.execute('''DELETE FROM epgtags;''')
      log('''Executing query: "DELETE FROM epgtags;"''')
      conn.execute('''DELETE FROM lastepgscan;''')
      log('''Executing query: "DELETE FROM lastepgscan;"''')
      conn.execute('''VACUUM;''')
      log('''Executing query: "VACUUM;"''')
      conn.commit()
  else:
    log("DB file not found! %s" % db_file)

###################################################
### Settings and variables 
###################################################
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_name = addon.getAddonInfo('name').decode('utf-8')
clean_tvdb = addon.getSetting('clean_tvdb') == 'true'
clean_epgdb = addon.getSetting('clean_epgdb') == 'true'
c_debug = True if addon.getSetting('debug') == 'true' else False
profile_dir = xbmc.translatePath( addon.getAddonInfo('profile') ).decode('utf-8')
db_dir = os.path.join(profile_dir, "../../Database/").decode('utf-8')
add_missing = True if addon.getSetting('add_missing') == 'true' else False
hide_lq_channels = True if addon.getSetting('hide_lq') == 'true' else False
hidden_groups = []
sorting = True
EXTINF = '#EXTINF:-1 radio="%s" tvg-id="%s" group-title="%s" tvg-logo="%s",%s\n'
pl_name = 'bgpl.m3u'
source_m3u = ''
new_m3u = os.path.join(profile_dir, pl_name)
log('new_m3u: %s' % new_m3u)
progress = 0
raw_radio_streams = ""

########################################
### Run addon only if PVR is not active
########################################
if is_player_active():
  xbmc.log("PVR is in use. Delaying playlist regeneration with 5 minutes")
  xbmc.executebuiltin('AlarmClock(%s, RunScript(%s, False), %s, silent)' % (addon_id, addon_id, 5))
else:
  ### Get channel groups that will be hidden
  if addon.getSetting('hide_children') == 'true':
    hidden_groups.append('Детски') 
  if addon.getSetting('hide_docs') == 'true':
    hidden_groups.append('Документални') 
  if addon.getSetting('hide_french') == 'true':
    hidden_groups.append('Френски') 
  if addon.getSetting('hide_english') == 'true':
    hidden_groups.append('Английски') 
  if addon.getSetting('hide_german') == 'true':
    hidden_groups.append('Немски') 
  if addon.getSetting('hide_holland') == 'true':
    hidden_groups.append('Холандски') 
  if addon.getSetting('hide_italian') == 'true':
    hidden_groups.append('Италиански') 
  if addon.getSetting('hide_movies') == 'true':
    hidden_groups.append('Филми') 
  if addon.getSetting('hide_music') == 'true':
    hidden_groups.append('Музикални') 
  if addon.getSetting('hide_news') == 'true':
    hidden_groups.append('Новини') 
  if addon.getSetting('hide_russian') == 'true':
    hidden_groups.append('Руски') 
  if addon.getSetting('hide_serbian') == 'true':
    hidden_groups.append('Сръбски') 
  if addon.getSetting('hide_theme') == 'true':
    hidden_groups.append('Тематични') 
  if addon.getSetting('hide_turkish') == 'true':
    hidden_groups.append('Турски') 
  if addon.getSetting('hide_xxx') == 'true':
    hidden_groups.append('Възрастни') 
  if addon.getSetting('hide_sports') == 'true':
    hidden_groups.append('Спортни') 
  if addon.getSetting('hide_bulgarian') == 'true':
    hidden_groups.append('Български') 
  if addon.getSetting('hide_others') == 'true':
    hidden_groups.append('Други')

  hg = "Следните групи канали ще бъдат скрити: "
  for h in hidden_groups:
    hg += "%s, " % h
  log(hg)

  ################################################
  ### Export channel names from original playlist
  ################################################
  export_names = True if addon.getSetting('export_names') == 'true' else False
  if export_names:
    export_to_folder = addon.getSetting('export_to_folder')
    if os.path.isdir(export_to_folder):
      names_file = os.path.join(export_to_folder, 'names.txt')
    else:
      names_file = os.path.join(profile_dir, 'names.txt')

  order_file = addon.getSetting('order_file')
  if not os.path.isfile(order_file):
    cwd = xbmc.translatePath( addon.getAddonInfo('path') ).decode('utf-8')
    order_file = os.path.join(cwd, 'resources', 'order.txt')
  log('order_file: %s' % order_file)

  if addon.getSetting('firstrun') == 'true':
    addon.setSetting('firstrun', 'false')
    addon.openSettings()
  
  #####################################################
  ### If addon is run manually display progress dialog
  #####################################################
  is_manual_run = False if len(sys.argv) > 1 and sys.argv[1] == str(False) else True
  if not is_manual_run:
    log('Автоматично генериране на плейлиста')
  dp = False
  update('operation', 'regeneration')
  if is_manual_run or c_debug:
    dp = xbmcgui.DialogProgressBG()
    dp.create(heading = addon_name)

  ###################################################
  ### Get playlist from source (server or file) and parse it (sort channels)
  ###################################################
  try:
    is_pl_remote = addon.getSetting('m3u_path_type') == '1'
    m3u_file = addon.getSetting('m3u_url') if is_pl_remote else addon.getSetting('m3u_path')
    log("Път до оригинална m3u плейлиста: " + m3u_file)

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
  xbmc.executebuiltin('AlarmClock(%s, RunScript(%s, False), %s, silent)' % (addon_id, addon_id, roi))
  
  ####################################################
  ###Restart PVR Service to reload channels' streams
  ####################################################
  if not is_player_active():
    xbmc.executebuiltin('XBMC.StopPVRManager')
    xbmc.sleep(1000)
    if clean_tvdb:
      delete_tvdb()
      xbmc.sleep(1000)
    if clean_epgdb:
      delete_epgdb()
      xbmc.sleep(1000)
    xbmc.executebuiltin('XBMC.StartPVRManager')
    #cursor2 = conn.execute('''SELECT sChannelName FROM channels WHERE iUniqueId = 9664925;''')
    #for row in cursor2:
    #  xbmc.log("curors %s" % row[0])

    #xbmc.sleep(1000)

  if dp:
    dp.close()