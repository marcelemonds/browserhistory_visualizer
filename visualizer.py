import sys
import os
import sqlite3
from urllib.parse import urlparse
from datetime import datetime
import socket
import ipinfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from progress.bar import Bar
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt


def get_ip_details(handler, ip):
    try:
        details = handler.getDetails(ip)
        return details.all
    except:
        return


def get_operating_system():
    print('')
    print('GETTING OPERATING SYSTEM')
    operating_systems = {
        'cygwin': 0,
        'win32': 0
        }

    try:
        os_code = operating_systems[sys.platform]
        print(f'OS: {sys.platform}')
        print(f'OS code: {os_code}')
    except KeyError:
        print(f'Error: Your operating system {sys.platform} is not supported.')
        exit()

    return os_code


def get_database_paths(os_code):
    print('')
    print('GETTING DATABASE PATHS')
    database_paths = dict()
    # OS: windows
    if os_code == 0:
        home_dir = os.path.expanduser('~')
        chrome_dir = os.path.join(home_dir, 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
        firefox_dir = os.path.join(home_dir, 'AppData', 'Roaming', 'Mozilla', 'Firefox', 'Profiles')
        # Browser: chrome
        if os.path.exists(chrome_dir):
            filenames = os.listdir(chrome_dir)
            # check for different profiles
            print('chrome:')
            for filename in filenames:
                if 'Profile ' in filename:
                    database_path = os.path.join(chrome_dir, filename, 'History')
                    if 'chrome' in database_paths:
                        database_paths['chrome'].append(database_path)
                    else:
                        database_paths['chrome'] = [database_path]
                    print(f'    - {database_path}')
            if not database_paths:
                database_path = os.path.join(home, 'Default', 'History')
                database_paths['chrome'] = [database_path]
                print(f'    - {database_path}')
        # Browser: firefox
        if os.path.exists(firefox_dir):
            print('firefox:')
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
                        print(f'    - {database_path}')

    return database_paths


def get_browserhistory(database_paths):
    print('')
    print('GETTING BROWSER HISTORY')

    browserhistory = dict()

    if database_paths:
        for browser, paths in database_paths.items():
            results = []
            bar = Bar(f'getting history from {browser} database paths', max=len(paths))
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
                    except sqlite3.OperationalError:
                        print(f'Error: Please close the open {browser} window.')
                        # exit()
                    except Exception as e:
                        print(path)
                        print(e)
                    cursor.close()
                    conn.close()
                    bar.next()
                except Exception as e:
                    print(e)
                bar.finish()
            browserhistory[browser] = results
        return browserhistory
    else:
        print('Error: No browserhistory databases found.')
        exit()


def prep_browserhistory(browserhistory):
    print('')
    print('GETTING HOSTS FROM DOMAINS')
    futures = list()
    ip_addresses = set()
    messages = list()
    for browser, entries in browserhistory.items():
        with ThreadPoolExecutor(max_workers=10) as e:
            bar = Bar(f'getting {browser} ip addresses:', max=len(entries))
            for entry in entries:
                try:
                    domain = urlparse(entry[0]).netloc.replace('www.', '').split(':')[0]
                    futures.append(socket.gethostbyname(domain))
                    bar.next()
                except socket.gaierror as e:
                    messages.append(f'Error: Could not get host for {domain} ({e})')
                except Exception as e:
                    print(e)
            bar.finish()
            for future in futures:
                ip_addresses.add(future)
    for message in messages:
        print(message)
    return ip_addresses


def prep_geo_data(access_token, ip_addresses):
    print('')
    print('GETTING GEO DATA FOR HOSTS')
    handler = ipinfo.getHandler(access_token)
    futures = list()
    geo_data = list()
    with ThreadPoolExecutor(max_workers=10) as e:
        bar = Bar('getting hosts details from ipinfo.io', max=len(ip_addresses))
        for ip in ip_addresses:
            futures.append(e.submit(get_ip_details, handler, ip))
            bar.next()
        bar.finish()
        for future in as_completed(futures):
            try:
                longitude = float(future.result()['longitude'])
                latitude = float(future.result()['latitude'])
                geo_data.append([longitude, latitude])
            except TypeError:
                print(f'Error: No ipinfo.io data for {future.result()}')
            except Exception as e:
                print(e)

    return geo_data


def get_visualization(geo_data):
    print('')
    print('CREATING WORLD MAP')
    basedir = os.path.abspath(os.path.dirname(__file__))
    plt.figure(figsize=(50, 50))
    world_map = plt.axes(projection=ccrs.PlateCarree())
    world_map.add_feature(cfeature.LAND)
    world_map.add_feature(cfeature.OCEAN)
    world_map.add_feature(cfeature.COASTLINE)
    world_map.add_feature(cfeature.BORDERS, linestyle=':')
    bar = Bar('plotting host locations', max=len(geo_data))
    for i in geo_data:
        world_map.scatter(i[0], i[1])
        bar.next()
    bar.finish()
    print('saving world map')
    plt.savefig(os.path.join(basedir, 'world_map.png'))


def visualize(access_token):
    os_code = get_operating_system()
    database_paths = get_database_paths(os_code)
    browserhistory = get_browserhistory(database_paths)
    ip_addresses = prep_browserhistory(browserhistory)
    geo_data = prep_geo_data(access_token, ip_addresses)
    get_visualization(geo_data)
    print('')
    print('WORLD MAP IS READY')
    return
