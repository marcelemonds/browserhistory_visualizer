import sys
import os
import sqlite3


operating_systems = {
        'cygwin': 0,
        'win32': 0
        }

try:
    os_code = operating_systems[sys.platform]
except KeyError:
    print(sys.exc_info()[0])
    print('Your operating system is not supported.')
    exit()

database_paths = dict()

if os_code == 0:
    home_dir = os.path.expanduser('~')
    chrome_dir = os.path.join(home_dir, 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
    firefox_dir = os.path.join(home_dir, 'AppData', 'Roaming', 'Mozilla', 'Firefox', 'Profiles')
    # chrome
    if os.path.exists(chrome_dir):
        filenames = os.listdir(chrome_dir)
        # check for different profiles
        for filename in filenames:
            if 'Profile ' in filename:
                profile_path = os.path.join(chrome_dir, filename, 'History')
                if 'chrome' in database_paths:
                    database_paths['chrome'].append(profile_path)
                else:
                    database_paths['chrome'] = [profile_path]
        if not database_paths:
            database_paths['chrome'] = [os.path.join(home, 'Default', 'History')]
    # firefox
    if os.path.exists(firefox_dir):
        filenames = os.listdir(firefox_dir)
        for filename in filenames:
            if '.default' in filename:
                profile_path = os.path.join(firefox_dir, filename)
                if 'places.sqlite' in os.listdir(profile_path):
                    database_path = os.path.join(profile_path, 'places.sqlite')
                    if 'firefox' in database_paths:
                        database_paths['firefox'].append(database_path)
                    else:
                        database_paths['firefox'] = [database_path]

browserhistory = {}

for browser, paths in database_paths.items():
    results = []
    for path in paths:
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            _SQL = ''

            if browser == 'chrome':
                _SQL = """SELECT url, title, datetime((last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime') 
                                    AS last_visit_time FROM urls ORDER BY last_visit_time DESC"""
            elif browser == 'firefox':
                _SQL = """SELECT url, title, datetime((visit_date/1000000), 'unixepoch', 'localtime') AS visit_date 
                                    FROM moz_places INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id ORDER BY visit_date DESC"""
            
            try:
                cursor.execute(_SQL)
                results.append(cursor.fetchall())
            except sqlite3.OperationalError as e:
                print('--------------- WARNING ---------------')
                print(f'Please close the open {browser} window.')
                print(e)
                print('---------------------------------------')
            except Exception as e:
                print(path)
                print(e)
            cursor.close()
            conn.close()
        except Exception as e:
            print(e)
    browserhistory[browser] = results
