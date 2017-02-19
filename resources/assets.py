# -*- coding: utf8 -*-
import os, sys, gzip, urllib2, urlparse, json, tempfile

### Basic class to download assets on a give time interval
### If download fails, and the old file doesn't exist
### Use a local file

class Asset:

  interval = 24 # Hours Interval to check for new version of the asset
  url = None # URL of the online resources
  url_md5 = None # MD5 sum of the online resource
  temp_dir = tempfile.gettempdir() # Directory where the file will be saved (downloaded and unzipped)
  file_name = None # The file name of the asset
  file = None # Path to the asset file 
  file_md5 = None # MD5 sum of the file
  backup_file = None # File that will be used in case the online asset is missing or couldn't be downloaded
  log = print # Callback funciton handling the logging
  first_run = False
  
  def __init__(self, url, **kwargs):
    """Create a new asset from an online file.
    if the local file is older than the 'interval' compare the local file md5 with the online file md5
    If md5 differs, download the file 
    """
    if url is '':
      raise ValueError("Valid asset url must be provided!")
    
    if kwargs is not None:
      self.log("**kwargs:")
      for key, value in kwargs.iteritems():
        self.log("%s: %s" % (key, value))
        if key is 'temp_dir':
          temp_dir = value
        
    if temp_dir not None:
      if os.path.isdir(temp_dir) is False:
        self.create_dir(temp_dir)
    
    self.temp_dir = temp_dir
    self.url = url
    self.url_path = urlparse.urlsplit(url).path
    
    if log_callback not None:
      self.log = log_callback

    self.url_md5 = urlparse.urljoin(self.url_path, '.md5')
    self.file_name = os.path.basename(url)
    self.file = os.path.join(temp_dir, self.file_name)
    self.file_md5 = os.path.join(self.file, '.md5')
    self.backup_file = backup_file
    if os.path.isfile(self.file):
      self.first_run = False
    if self.is_timer_expired():
      self.get_asset()
    if self.file.endswith('gz'):
      self.extract()   
    
  def get_json(self):
    try:
      with open(self.file) as f:
        return json.loads(f.read())
    except:
      self.log("Unable to load JSON content from file %s" % self.file)
      self.handle_ex()
      return {}
      
  def get_md5(self):
    try: 
      with open(self.file_md5) as f:
        return f.read()
    except:
      self.log("Unable to read %s" % self.file_md5)
      return 'default_md5_old'
 
  def get_new_md5(self):
    try:
      self.log('Checking asset md5: %s' % self.url_md5)
      f = urllib2.urlopen(self.url)
      return f.read()
    except:
      log('Unable to read online md5 sum %s' % self.url_md5)
      return 'default_md5_new'
      
  def create_dir(self, dir):
    try: os.makedirs(dir)
    except OSError as exc: # Guard against race condition
      if exc.errno != errno.EEXIST:
        raise
  
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
        return False
      else: #file does not exist, perhaps first run
        return True
    except Exception, er:
      self.log(str(er), 4)
      return True

  #######################################################
  ### Downloads asset only if md5 sum differs
  #######################################################
  def get_asset(self):
    try:
      new_md5 = self.get_new_md5()
      old_md5 = self.get_md5()
      
      if new_md5 != old_md5:
        self.log('Downloading assets from url: %s' % self.url)
        f = urllib2.urlopen(self.url)
        with open(self.file, "wb") as w:
          w.write(f.read())
        self.log('Assets file downloaded')
        with open(self.file_md5, "w") as f:
          f.write(new_md5)
      else:
        self.log('md5 has not changed. File download skipped')
    except:
      self.handle_ex()
      
  def extract(self):
    try:
      gz = gzip.GzipFile(self.file, 'rb')
      s = gz.read()
      gz.close()
      self.file = self.file.replace('.gz', '')
      with file(self.file, 'wb') as out:
        out.write(s)
    except:
      self.handle_ex()
      
  def handle_ex(self):
    import traceback
    type, errstr = sys.exc_info()[:2]
    self.log('Unable to download assets file!\n' + str(sys.exc_info()[0]) + ': ' + str(sys.exc_info()[1]) + ''.join(traceback.format_stack()), 4)
    if not os.path.isfile(self.file) and os.path.isfile(self.backup_file): #if asset was never downloaded and backup exists
      self.file = self.backup_file