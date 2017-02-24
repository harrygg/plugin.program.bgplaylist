# -*- coding: utf8 -*-
import os
import sys
import gzip
import urllib2
import urlparse
import json
import tempfile
import hashlib
import shutil
from datetime import datetime

class Asset():

  interval = 24 # Hours Interval to check for new version of the asset
  
  def __init__(self, url, **kwargs):
    """Create a new asset from an online file.
    if the local file is older than the 'interval' compare the local file md5 with the online file md5
    If md5 differs, download the file 
    """
    if url is '':
      raise ValueError("Valid asset url must be provided!")
    self.url = url
    self.url_md5 = url + ".md5"
    #self.url_path = urlparse.urlsplit(url).path
    
    # Directory where the file will be saved (downloaded and unzipped)
    self.temp_dir = kwargs.get('temp_dir', tempfile.gettempdir()) 
    # File that will be used in case the online asset is missing or couldn't be downloaded
    self.backup_file = kwargs.get('backup_file', None)
    # Log enabled? 
    self.enable_log = kwargs.get('enable_log', True) 
    # Callback funciton handling the logging
    self.log_callback = kwargs.get('log_callback', None)
    # Try to update automatically    
    self.autoupdate = kwargs.get('autoupdate', True) 
    
    # Create temp dir
    if self.temp_dir is not None:
      if os.path.isdir(self.temp_dir) is False:
        self.create_dir(self.temp_dir)
    
    self.file_name = os.path.basename(url)
    self.file = os.path.join(self.temp_dir, self.file_name)
    self.file_md5 = self.file + ".md5"
    
    if self.autoupdate:
      if self.is_expired():
          self.get_asset()  
  
  def log(self, msg):
    if self.enable_log:
      if self.log_callback is None:
        print(msg)
      else:
        self.log_callback(msg)
  
  def get_json(self):
    try:
      with open(self.file) as f:
        return json.loads(f.read())
    except:
      self.log("Unable to load JSON content from file %s" % self.file)
      self.handle_exception()
      return {}
      
  def get_md5(self):
    try:
      return hashlib.md5(open(self.file, 'rb').read()).hexdigest()
    except:
      return 'default_md5_old'
 
  def get_new_md5(self):
    try:
      self.log('Checking asset md5: %s' % self.url_md5)
      f = urllib2.urlopen(self.url_md5)
      return f.read()
    except:
      self.log('Unable to read online md5 sum %s' % self.url_md5)
      return 'default_md5_new'
      
  def create_dir(self, dir):
    try: os.makedirs(dir)
    except OSError as exc: # Guard against race condition
      if exc.errno != errno.EEXIST:
        raise
  
  
  def is_expired(self):
    return self.is_timer_expired() and self.get_md5() is not self.get_new_md5()
  
  #######################################################
  ### Checks if file is modified only on a given interval
  #######################################################
  def is_timer_expired(self):
    try:
      from datetime import datetime, timedelta
      if os.path.isfile(self.file):
        treshold = datetime.now() - timedelta(hours=self.interval)
        modified = datetime.fromtimestamp(os.path.getmtime(self.file))
        if modified < treshold: #file is more than a day old
          return True
        #Check if the file is older than the backup file (in case of addon update)
        backup_modified = datetime.fromtimestamp(os.path.getmtime(self.backup_file))
        #self.log("backup_modified: " + str(backup_modified))
        if modified < backup_modified:
          self.log("File is older than backup file")
          return True
        return False
      else: #file does not exist, perhaps first run
        return True
    except Exception, er:
      self.log(str(er))
      return True

  #######################################################
  ### Downloads asset only if md5 sum differs
  #######################################################
  def get_asset(self):
    try:      
      self.log('Downloading assets from url: %s' % self.url)
      f = urllib2.urlopen(self.url)
      with open(self.file, "wb") as w:
        w.write(f.read())
      self.log('Assets file saved to %s' % self.file)
      if self.file.endswith('gz'):
        self.extract() 
    except:
      self.handle_exception()
      
  def extract(self):
    try:
      gz = gzip.GzipFile(self.file, 'rb')
      s = gz.read()
      gz.close()
      self.file = self.file.replace('.gz', '')
      with file(self.file, 'wb') as out:
        out.write(s)
    except:
      self.handle_exception()
      
  def handle_exception(self):
    import traceback
    type, errstr = sys.exc_info()[:2]
    self.log('Unable to download assets file!\n' + str(sys.exc_info()[0]) + ': ' + str(sys.exc_info()[1]) + ''.join(traceback.format_stack()))
    ### If file doesn't exist or is older than backup_file, replace it
    if not os.path.isfile(self.file):
      shutil.copyfile(self.backup_file, self.file)
    else:
      modified_file = datetime.fromtimestamp(os.path.getmtime(self.file))
      modified_backup = datetime.fromtimestamp(os.path.getmtime(self.backup_file))
      if modified_file < modified_backup:
        shutil.copyfile(self.backup_file, self.file)
