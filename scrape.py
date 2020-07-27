import requests, re, pprint, pandas as pd, json, PyPDF2, os

from bs4 import BeautifulSoup
from collections import OrderedDict

code_map = {'CCST': 'Science and Technology', 'CCGL': 'Global Issues', 'CCHU': 'Humanities', 'CCCH': 'China'}

#Get the URLs of the pages
def get_area_urls(filename = 'area-pages.txt'):
    #Load the urls file
    with open(filename, 'r') as f:
        urls = f.readlines()
    
    #Filter out blank lines and lines starting with #
    urls = [url.strip() for url in urls if url.strip() and not url.startswith('#')]
    
    return urls

#Download course timetable
def get_timetable(filename = 'timetable-page.txt'):
    with open(filename, 'r') as f:
        url = f.readlines()[0]
    
    r = requests.get(url)

    with open('timetable.pdf', 'wb') as f:
        f.write(r.content)
    
    lines = []
    with open('timetable.pdf', 'rb') as f:
        pdf = PyPDF2.PdfFileReader(f)
        for page in range(pdf.numPages):
            lines.extend([line.strip() for line in pdf.getPage(page).extractText().split('\n')])

    os.remove('timetable.pdf')

    code = re.compile("CC[SHGC][TULH][0-9]{4}")
    time = re.compile("[0-9]{2}:[0-9]{2} - [0-9]{2}:[0-9]{2}")

    keys = []
    values = []

    for i, v in enumerate(lines):
        if (code.search(v)):
            keys.append(v[:8])
        elif (time.search(v)):
            values.append(lines[i + 1].strip() if lines[i + 1].strip() in ['Online', 'Mixed'] else 'Offline')

    isOnline = dict((keys[i], values[i]) for i in range(len(keys)))
    
    return isOnline
    
#Get the link to every course from a certain area of inquiry/URL
def get_all_cc_links(url):
    links = []

    r = requests.get(url)
    r.raise_for_status()

    html_content = r.content

    soup = BeautifulSoup(html_content, features = 'html.parser')

    for link in soup.find_all('a'):
        #Check if link is to a CC
        cc_reg = re.compile(r'/cc[shgc][tulh][0-9]{4}')
        if cc_reg.search(link['href']):
            links.append(f'https://commoncore.hku.hk{link["href"]}')        

    return links

#Scrape the details of a single CC
def scrape_cc(url, onlineDict):
    try:
        content = OrderedDict()
        
        r = requests.get(url)
        r.raise_for_status()

        html_content = r.content

        soup = BeautifulSoup(html_content, features = 'html.parser')

        content['Code'] = url.rsplit('/', maxsplit = 1)[1].upper()
        content['Link'] = url

        #Get course name
        content['Name'] = soup.find('title').text.rsplit('|', maxsplit = 1)[0].split('-', maxsplit = 1)[1].strip()
        
        content['Area of Inquiry'] = code_map[content['Code'][:4]]

        #Get offer semester
        content['Semesters'] = []
        offered_in = soup.find(id = 'osdt').findNext('p').text

        if 'First' in offered_in:
            content['Semesters'].append('1')
        if 'Second' in offered_in:
            content['Semesters'].append('2')
        
        #Get coursework percentage
        amt_string = soup.find(id = 'ass').text.split(':', maxsplit = 1)[1].strip()
        first_percent = int(amt_string[:amt_string.index('%')])
        percent_type = amt_string.split('%', maxsplit = 1)[1].strip()[0]

        #If the percentage type isn't coursework, get the coursework percentage
        if percent_type != 'c':
            first_percent = 100 - first_percent

        content['Coursework Percentage'] = first_percent

        #Get table of assessments
        amt_table_str = str(soup.find(id = 'ass').findNext('table'))
        amt_pd_table = pd.read_html(amt_table_str, header = 0)[0].set_index('Assessment Tasks').dropna().to_dict()
        amt_methods = amt_pd_table['Weighting']
        amt_methods_header = OrderedDict()
        for k, v in amt_methods.items():
            amt_methods_header[k] = v

        #Get study load table
        study_load_table_str = str(soup.find(id = 'load').findNext('table'))
        study_load_pd_table = pd.read_html(study_load_table_str, header = 0)[0].set_index('Activities').dropna().to_dict()
        study_load = study_load_pd_table['Number of hours']
        study_load_header = OrderedDict()
        for k, v in study_load.items():
            study_load_header[k] = v

        content['Study hours'] = study_load['Total:']
        study_load.pop('Total:')

        content['Delivery mode'] = onlineDict[content['Code']]

        return [content, amt_methods_header, study_load_header]
    except:
        return [None, url[-8:].upper()]

#Save a course to file
def save_to_file(course, success_filename = 'valid_courses.txt', fail_filename = 'invalid_courses.txt'):
    if course[0]:
        with open(success_filename, 'a+') as f:
            for section in course:
                f.write(json.dumps(section) + '\n')

            f.write('\n')
    else:
        with open(fail_filename, 'a+') as f:
            f.write(course[1] + '\n')

if __name__ == '__main__':
    onlineDict = get_timetable()
    for area in get_area_urls():
        for link in get_all_cc_links(area):
            save_to_file(scrape_cc(link, onlineDict))
