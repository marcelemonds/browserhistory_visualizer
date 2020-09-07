import sys
import os
import sqlite3
from urllib.parse import urlparse
from datetime import datetime
import socket
import ipinfo
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_ip_details(ip):
    try:
        details = handler.getDetails(ip)
        return details.all
    except:
        return


def get_operating_system():
    operating_systems = {
        'cygwin': 0,
        'win32': 0
        }

    try:
        os_code = operating_systems[sys.platform]
    except KeyError:
        print('---------------- ERROR ----------------')
        print('Your operating system is not supported.')
        print(sys.exc_info()[0])
        print('---------------------------------------')
        exit()

    return os_code


def get_database_paths(os_code):
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

    return database_paths


def get_browserhistory(database_paths):

    browserhistory = dict()

    if database_paths:
        for browser, paths in database_paths.items():
            results = []
            for path in paths:
                try:
                    conn = sqlite3.connect(path)
                    cursor = conn.cursor()
                    sql_statement = ''

                    if browser == 'chrome':
                        sql_statement = """SELECT url, title, datetime((last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime') 
                                            AS last_visit_time FROM urls ORDER BY last_visit_time DESC"""
                    elif browser == 'firefox':
                        sql_statement = """SELECT url, title, datetime((visit_date/1000000), 'unixepoch', 'localtime') AS visit_date 
                                            FROM moz_places INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id ORDER BY visit_date DESC"""
                    
                    try:
                        cursor.execute(sql_statement)
                        results.extend(cursor.fetchall())
                    except sqlite3.OperationalError as e:
                        print('--------------- ERROR ---------------')
                        print(f'Please close the open {browser} window.')
                        print(e)
                        print('---------------------------------------')
                        # exit()
                    except Exception as e:
                        print(path)
                        print(e)
                    cursor.close()
                    conn.close()
                except Exception as e:
                    print(e)
            browserhistory[browser] = results
        return browserhistory
    else:
        print('--------------- ERROR ---------------')
        print('No browserhistory databases found.')
        print('-------------------------------------')
        exit()


def prep_browserhistory(browserhistory):
    data_all = dict()
    data_ips = set()

    for browser, entries in browserhistory.items():
        if browser not in data_all:
            data_all[browser] = {'entries':{}}

        for index, entry in enumerate(entries):
            try:
                domain = urlparse(entry[0]).netloc.replace('www.', '').split(':')[0]
                ip = socket.gethostbyname(domain)
                data_ips.add(ip)
                date = datetime.strptime(entry[2], '%Y-%m-%d %H:%M:%S').date()
                if index == 0:
                    data_all[browser]['start'] = date
                    data_all[browser]['end'] = date

                if date < data_all[browser]['start']:
                    data_all[browser]['start'] = date
                elif date > data_all[browser]['end']:
                    data_all[browser]['end'] = date

                if domain not in data_all[browser]['entries']:
                    data_all[browser]['entries'][domain] = [ip, 1]
                else:
                    data_all[browser]['entries'][domain][1] += 1
            except socket.gaierror as e:
                print(f'Error: Could not get host for {domain} ({e})')
            except Exception as e:
                print(e)

    return data_all, data_ips


def get_ip_details(access_token=None, data_ips):
    if access_token is None:
        print('--------------- ERROR ---------------')
        print('No access token for ipinfo.io provided.')
        print('-------------------------------------')
        exit()

    handler = ipinfo.getHandler(access_token)

    complete_details = list()
    with ThreadPoolExecutor(max_workers=10) as e:
        for ip in data_ips:
            complete_details.append(e.submit(get_ip_details, ip))

    return complete_details

# print(complete_details)