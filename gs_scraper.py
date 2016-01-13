# Erik Jensen ejens005@odu.edu
# Old Dominion University
# Dept. of Computer Science
# WS-DL Research Group
# October 26, 2015
# gs_scraper.py
# Python 3.4

# This script can:
#       (1) take a single author name in the command line and generate separate lists
#           of most cited papers and most recent papers.
#       (2) take a group of authors from an input file and generate separate lists of
#           the group's most cited papers and most recent papers.
#               - Exclusions may be applied to avoid papers beyond the scope of the group.

# Usage:    python3 gs_scraper.py input_file
#               - read a list of authors and GS profile page URLs from an input file
#           python3 gs_scraper.py name
#               - input a single author's last name or first and last names or full name
# Optional: Usage + "bycitations"
#               - search only by number of citations, descending sort
#           Usage + "byyear"
#               - search only by year, descending sort
#           Usage + "start" specific_year
#               - exclude papers dated before specific_year
#           Usage + "max" number_papers
#               - set upper limit to number of papers

# Input file entry format:  (1) group_name, URL:url\n
#                               author1_first author1_last\n
#                               author2_first author2_last\n
#                               ...
#                           (2) group_name, URL:url, Keyword Exclusions:phrase1, phrase2, ... phraseN...\n
#                               author1_first author1_last\n
#                               author2_first author2_last\n
#                               ...

# Third-party libraries:
#   (1) Requests
#       - HTML data retrieval
#       - https://github.com/kennethreitz/requests
#   (2) html5lib-python
#       - HTML file parsing
#       - https://github.com/html5lib/html5lib-python
#   (3) Beautiful Soup 4.4.0
#       - HTML data extraction and organization
#       - http://www.crummy.com/software/BeautifulSoup

# **************************************************************************************************************

from bs4 import BeautifulSoup       # HTML data extraction and organization library
import requests                     # HTML data retrieval library
import sys
import os.path
import time
import random
from datetime import date

# # *** testing mode ***
g_testing = False


class Paper:
    def __init__(self, author_name, title, url, year, citations, faculty, out_file):
        self.author_name = author_name
        self.title = title
        self.url = url
        self.year = year
        self.citations = citations
        self.faculty = faculty
        self.out_file = out_file
        self.source = ''
        self.author_names = ''
        self.author_links = ''

    # # *** get coauthors from GS paper page ***
    # get links for authors from ODU CS department
    def scrape_additional_paper_info(self):
        author_links = ''
        source = ''

        if g_testing:
            filename = self.title.replace(' ', '_').replace('/', '_slash_')[:200] + '.html'
            if not os.path.isfile(filename):
                paper_soup = get_soup(self.url)
                soup_file = open(filename, 'w')
                soup_file.write(str(paper_soup))
                soup_file.close()
            else:
                soup_file = open(filename, 'r')
                html = soup_file.read()
                paper_soup = BeautifulSoup(html, 'html5lib')
        else:
            paper_soup = get_soup(self.url)

        # find coauthors
        first_field = paper_soup.find('div', class_='gs_scl').find('div', 'gsc_field')
        if first_field.string == 'Authors':                                     # if GS page has "Authors" field
            authors = first_field.nextSibling.string
            self.author_names = authors
            num_authors = authors.count(',') + 1
            for i in range(0, num_authors):
                author = authors.split(',')[i].strip()
                if len(author_links) > 0:
                    author_links += ', '
                member = get_faculty_member(author, self.faculty, True)
                if member is not None:
                    cs_url = member.cs_url
                    author_links += '<a href=' + cs_url + '>' + author + '</a>'
                else:
                    author_links += author
        # look for coauthors in "Scholar articles" field
        else:
            all_rows = paper_soup.find_all('div', class_='gs_scl')
            for row in all_rows:
                field = row.find('div', 'gsc_field')
                if field.string == 'Scholar articles':
                    field_values = field.nextSibling.find_all('div', class_='gsc_merged_snippet')
                    for value in field_values:
                        paper_info = value.find_all('div')[1]
                        author_last_name = self.author_name.split(' ')[self.author_name.count(' ')]
                        if author_last_name in paper_info.string:
                            authors = paper_info.string.split('-')[0]
                            num_authors = authors.count(',') + 1
                            for i in range(0, num_authors):
                                author = authors.split(',')[i].strip()
                                if len(author_links) > 0:
                                    author_links += ', '
                                member = get_faculty_member(author, self.faculty, True)
                                if member is not None:
                                    full_name = member.name
                                    cs_url = member.cs_url
                                    author_links += '<a href=' + cs_url + '>' + full_name + '</a>'
                                else:
                                    author_links += author
        # look for source in "Book", "Conference", "Journal" field
        all_rows = paper_soup.find_all('div', class_='gs_scl')
        for row in all_rows:
            field = row.find('div', 'gsc_field')
            if field.string == 'Book' or field.string == 'Conference' or field.string == 'Journal':
                source = field.nextSibling.string

        self.source = source
        self.author_links = author_links

    def write_paper(self, citations_first):
        paper_title = modify_special_chars(self.title)
        paper_author_links = modify_special_chars(self.author_links)

        if citations_first:
            year_citations_string = str(self.citations) + ' ' + str(self.year)
        else:
            year_citations_string = str(self.year) + ' ' + str(self.citations)

        if not self.source == '':
            source_string = '<br>' + self.source
        else:
            source_string = ''

        self.out_file.write('\n<p>' + year_citations_string + ' ' + '<a href=' + self.url +
                            '>' + paper_title + '</a>' + source_string + '<br>' + paper_author_links + '</p>')


class Author:
    def __init__(self, name, cs_url, gs_url, citations_size, year_size, first_year, exclusion_set,
                 group, faculty, out_file):
        self.name = name
        self.cs_url = cs_url
        self.gs_url = gs_url
        self.citations_size = citations_size
        self.year_size = year_size
        self.first_year = first_year
        self.exclusion_set = exclusion_set
        self.group = group
        self.faculty = faculty
        self.out_file = out_file
        self.citations_papers = []
        self.year_papers = []
        self.gs_by_year_url = ''

    def set_citation_papers(self, papers):
        self.citations_papers = papers

    def set_year_papers(self, papers):
        self.year_papers = papers

    def set_gs_by_year_url(self, gs_by_year_url):
        self.gs_by_year_url = gs_by_year_url

    # # *** get author's most cited and/or most recent papers
    def scrape_author(self):

        print('AUTHOR: ' + self.name)

        if g_testing:
            filename = self.name.replace(' ', '_') + '_citations.html'
            if not os.path.isfile(filename):
                soup = get_soup(self.gs_url)
                soup_file = open(filename, 'w')
                soup_file.write(str(soup))
                soup_file.close()
            else:
                soup_file = open(filename, 'r')
                html = soup_file.read()
                soup = BeautifulSoup(html, 'html5lib')
        else:
            soup = get_soup(self.gs_url)

        # # *** most cited papers ***
        if self.citations_size > 0:
            print('\tSearching for papers by number of citations:')
            # get papers sorted by most cited
            citations_papers = self.scrape_papers(soup, self.citations_size)
            self.citations_papers = citations_papers

        # # *** most recent papers ***
        if self.year_size > 0:
            # extract the sort-by-year URL, discard first hit
            gs_by_year_url = 'https://scholar.google.com' + soup.find_all('a', class_='gsc_a_a')[1].get('href')
            self.set_gs_by_year_url(gs_by_year_url)

            if g_testing:
                filename = self.name.replace(' ', '_') + '_year.html'
                if not os.path.isfile(filename):
                    soup = get_soup(self.gs_by_year_url)
                    soup_file = open(filename, 'w')
                    soup_file.write(str(soup))
                    soup_file.close()
                else:
                    soup_file = open(filename, 'r')
                    html = soup_file.read()
                    soup = BeautifulSoup(html, 'html5lib')
            else:
                soup = get_soup(self.gs_by_year_url)

            print('\tSearching for papers by year:')
            year_papers = self.scrape_papers(soup, self.year_size)          # get papers sorted by most recent
            self.year_papers = year_papers

    # # *** get papers from the author's GS page ***
    def scrape_papers(self, soup, target_hits):
        papers = soup.find_all('a', class_='gsc_a_at')                      # search for papers by CSS class
        citations = soup.find_all('a', class_='gsc_a_ac')                   # search for citations by CSS class
        # search for years by CSS class, discard first hit
        years = soup.find_all('span', class_='gsc_a_h')[1:]
        paper_set = []
        for i in range(0, len(papers)):
            if int(years[i].string) >= self.first_year:
                paper_title = papers[i].string
                paper_excluded = False
                for keyword in self.exclusion_set:                          # look for exclusion keywords in title
                    if keyword.lower() in paper_title.lower():
                        paper_excluded = True
                if not paper_excluded:
                    # get paper URL
                    url = 'https://scholar.google.com' + papers[i].get('href')
                    # for papers with 0 citations, replace non-breaking space ' ' with '0'
                    num_citations = citations[i].string.replace(u'\xa0', u'0')
                    print('\n\t\tPAPER: ' + paper_title[:50])
                    print('\t\tYEAR: ' + years[i].string)
                    print('\t\tCITATIONS: ' + num_citations)

                    paper = Paper(self.name, paper_title, url, int(years[i].string), int(num_citations),
                                  self.faculty, self.out_file)
                    paper_set.append(paper)

            if len(paper_set) == target_hits:  # if target number reached
                break

        # randomly scrape coauthors
        paper_ids = list(range(0, len(paper_set)))
        for paper in paper_set:
            index = random.randint(0, len(paper_ids) - 1)
            paper_id = paper_ids[index]
            paper_ids.remove(paper_id)
            paper_set[paper_id].scrape_additional_paper_info()

        return paper_set

    def write_author(self):
        self.out_file.write('\n<h2><a href=' + self.cs_url + '>' +
                            modify_special_chars(self.name) + '</a>' + '</h2>')
        if self.citations_size > 0:
            self.out_file.write('\n<h3><a href=' + self.gs_url + '>' +
                                'Most Cited Papers' + '</a></h3>')
            self.out_file.write('\n<h4>Citations Year Title</h4>')
            for paper in self.citations_papers:
                paper.write_paper(True)

        if self.year_size > 0:
            self.out_file.write('\n<h3><a href=' + self.gs_by_year_url + '>' +
                                'Most Recent Papers' + '</a></h3>')
            self.out_file.write('\n<h4>Year Citations Title</h4>')
            for paper in self.year_papers:
                paper.write_paper(False)


class Group:
    def __init__(self, citations_size, year_size, group, first_year, faculty):
        with open(sys.argv[1], 'r') as in_file:
            group_info = in_file.readline()
            out_file = open(group_info.split(', URL:')[0].replace(' ', '_').strip() + '.html', 'w')
            out_file.write('<!DOCTYPE html>' + '\n<html>' + '\n<body>' +
                           '\n\n<h1>Old Dominion University</h1>' +
                           '\n<h1>Department of Computer Science</h1>' +
                           '\n<h1>Faculty Google Scholar Page Data</h1>' + '\n')  # begin HTML

            group_name = group_info.split(', URL:')[0].strip()
            group_url = 'http://www.cs.odu.edu'
            if ', URL:' in group_info:
                group_url = group_info.split(', URL:')[1].split(', Keyword Exclusions:')[0].strip()

            # determine if a set of exclusion keywords exists in input file
            # if so, send to Author object so papers can be excluded
            exclusion_set = []
            if ', Keyword Exclusions:' in group_info:
                exclusions = group_info.split(', Keyword Exclusions:')[1].strip()
                num_keywords = exclusions.count(',')
                for i in range(0, num_keywords + 1):
                    exclusion_set.append(exclusions.split(',')[i].strip())

            print('GROUP: ' + group_name)
            author_set = []
            max_citations_size = 20
            max_year_size = 20
            for author in in_file:
                member = get_faculty_member(author, faculty)
                author_set.append(Author(member.name, member.cs_url, member.gs_url, max_citations_size,
                                         max_year_size, first_year, exclusion_set, group, faculty, out_file))

        self.name = group_name
        self.url = group_url
        self.authors = author_set
        self.citations_size = citations_size
        self.year_size = year_size
        self.out_file = out_file
        self.citations_papers = []
        self.year_papers = []

    def add_author(self, author):
        self.authors.append(author)

    def set_citation_papers(self, papers):
        self.citations_papers = papers

    def set_year_papers(self, papers):
        self.year_papers = papers

    # # *** compile a set of the group's most cited papers ***
    def compile_citations_set(self):
        citations_papers = []
        for i in range(0, self.citations_size):
            max_citations = 0
            top_paper = None
            next_paper = None
            for author in self.authors:
                for paper in author.citations_papers:
                    if len(citations_papers) is 0:
                        if paper.citations >= max_citations:
                            top_paper = paper
                            max_citations = paper.citations
                    elif max_citations <= paper.citations <= citations_papers[i - 1].citations:
                        paper_already_included = False
                        for included_paper in citations_papers:
                            if paper.title.lower() == included_paper.title.lower():
                                paper_already_included = True
                                break
                        if not paper_already_included:
                            max_citations = paper.citations
                            next_paper = paper

            if top_paper is not None:
                citations_papers.append(top_paper)
            if next_paper is not None:
                citations_papers.append(next_paper)

        print('\n\tGetting author information for citations-ordered papers.')

        print("Group papers ordered by number of citations:")
        for paper in citations_papers:
            print('\n\tPAPER: ' + paper.title[:50])
            print('\tYEAR: ' + str(paper.year))
            print('\tCITATIONS: ' + str(paper.citations))
            print('\tAUTHORS: ' + paper.author_names[:50])

        self.citations_papers = citations_papers

    # # *** compile a set of the group's most recent papers ***
    # papers on GS are dated only by year, so no other information is known
    # algorithm attempts to fairly represent all group members
    def compile_year_set(self):

        year_today = date.today().year
        current_year = year_today
        original_max_papers_per_author = 1
        max_papers_per_author = original_max_papers_per_author

        # # *** compile set ***
        year_papers = []
        decrement_year_counter = 0
        while True:
            # # *** determine paper qty for author in current year ***
            paper_added = False
            author_qty_in_current_year = []
            for author in self.authors:
                papers_in_year = 0
                for paper in author.year_papers:
                    if paper.year == current_year:
                        papers_in_year += 1
                author_qty_in_current_year.append([author.name, papers_in_year])

            # # *** sort authors by productivity in current year ***
            # used to determine order in which authors are assessed
            authors_ranked_in_current_year = []
            max_num_papers = -1
            while len(authors_ranked_in_current_year) < len(author_qty_in_current_year):
                author_name = ''
                for i in range(0, len(author_qty_in_current_year)):
                    if author_qty_in_current_year[i][1] > max_num_papers:
                        candidate = author_qty_in_current_year[i][0]
                        author_already_included = False
                        for author in authors_ranked_in_current_year:
                            if candidate == author:
                                author_already_included = True
                        if not author_already_included:
                            author_name = candidate
                            max_num_papers = author_qty_in_current_year[i][1]

                authors_ranked_in_current_year.append(author_name)
                max_num_papers = -1

            for author_name in authors_ranked_in_current_year:
                for author in self.authors:
                    if author.name == author_name:
                        num_spaces_in_author_name = author.name.count(' ')
                        author_first_name = author.name.split(' ')[0]
                        author_last_name = author.name.split(' ')[num_spaces_in_author_name]

                        for paper in author.year_papers:
                            if len(year_papers) == self.year_size:
                                break
                            if paper.year == current_year:
                                paper_already_included = False
                                current_year_author_paper_count = 0
                                for included_paper in year_papers:
                                    if paper.title.lower() == included_paper.title.lower():
                                        paper_already_included = True
                                        break
                                    if author_last_name in included_paper.author_names and \
                                        author_first_name in included_paper.author_names and \
                                            paper.year == included_paper.year:
                                        current_year_author_paper_count += 1
                                if paper_already_included:
                                    continue
                                if 0 <= current_year_author_paper_count < max_papers_per_author:
                                    year_papers.append(paper)
                                    paper_added = True
                                break

                        if len(year_papers) == self.year_size:
                            break

            max_papers_per_author += 1
            if len(year_papers) == self.year_size:
                break
            if not paper_added:
                decrement_year_counter += 1
                if decrement_year_counter == len(self.authors):
                    current_year -= 1
                    max_papers_per_author = original_max_papers_per_author
                    decrement_year_counter = 0
            if current_year < year_today - 10:
                break

        print('\n\tGetting author information for year-ordered papers.')

        print("Group papers ordered by year:")
        for paper in year_papers:
            print('\n\tPAPER: ' + paper.title[:50])
            print('\tYEAR: ' + str(paper.year))
            print('\tCITATIONS: ' + str(paper.citations))
            print('\tAUTHORS: ' + paper.author_names[:50])

        self.year_papers = year_papers

    # # *** randomly scrape each author in group ***
    def scrape_authors(self):
        author_ids = list(range(0, len(self.authors)))
        for each in self.authors:
            index = random.randint(0, len(author_ids) - 1)
            author_id = author_ids[index]
            author_ids.remove(author_id)
            self.authors[author_id].scrape_author()

    # # *** write group info to HTML file ***
    def write_group(self):
        self.out_file.write('\n<h2><a href=' + self.url + '>' + modify_special_chars(self.name) + '</a>' + '</h2>')
        if self.citations_size > 0:
            self.out_file.write('\n<h3>Most Cited Papers</h3>')
            self.out_file.write('\n<h4>Citations Year Title</h4>')
            for paper in self.citations_papers:
                paper.write_paper(True)
        if self.year_size > 0:
            self.out_file.write('\n<h3>Most Recent Papers</h3>')
            self.out_file.write('\n<h4>Year Citations Title</h4>')
            for paper in self.year_papers:
                paper.write_paper(False)

        self.out_file.write('\n</body>' + '\n</html>')  # end HTML
        self.out_file.close()


# # *** name, CS URL, GS URL of faculty member ***
class FacultyMember:
    def __init__(self, name, cs_url, gs_url):
        self.name = name
        self.cs_url = cs_url
        self.gs_url = gs_url


# # *** convert special characters for use in HTML file ***
def modify_special_chars(string):
    mod_string = str(string.encode('ascii', errors='xmlcharrefreplace'))[2:-1]
    return mod_string


# # *** get faculty member full name, CS URL, GS URL ***
def get_faculty_member(name, faculty, coauthor=False):
    num_name_fields = name.count(' ') + 1                                   # count spaces in name
    name_fields = name.strip().split(' ')                                   # split name into fields
    # parse first and last names
    first_name, last_name = name_fields[0], name_fields[num_name_fields - 1]
    all_caps = True
    for letter in first_name:
        if not letter == letter.upper():
            all_caps = False
    # if name sourced from GS article page, "Scholar articles" field
    # first and/or middle name(s) abbreviated
    if all_caps:
        middle_init = ''
        if len(first_name) > 1:
            middle_init = first_name[1]
        for member in faculty:
            fac_middle_init = ''
            fac_num_name_fields = member.name.count(' ') + 1
            fac_name_fields = member.name.split(' ')
            if fac_num_name_fields > 2:
                fac_middle_init = fac_name_fields[1][0]
            if last_name in member.name and first_name[0] == member.name[0]:
                if not middle_init == '' and not fac_middle_init == '' and middle_init == fac_middle_init:
                    return member
                elif middle_init == '' or fac_middle_init == '':
                    return member
    else:                                                                   # name(s) not abbreviated
        for member in faculty:
            if last_name.lower() in member.name.lower() and first_name.lower() in member.name.lower():
                return member                                               # return member with matching names
    if not coauthor:                                                        # if name should be in faculty_info.txt
        print("Faculty member not found in faculty_info.txt.")
        print("Is that file out of date?")
        exit(1)
    return None


# # *** get Beautiful Soup object tree ***
def get_soup(url, pause=True):
    min_pause = 75
    max_pause = 150                                                         # pause time limits in seconds
    if pause:
        pause_time = random.uniform(min_pause, max_pause)                   # randomly pick pause time
        print('\t\t*** Pausing for ' + str(pause_time)[:5] + ' seconds... ***')
        time.sleep(pause_time)                                              # pause script to satisfy GS
    html_parser = 'html5lib'                                                # html5lib HTML parser
    # html_parser = 'html.parser'                                           # Python's HTML parser

    # appear to be a web browser
    user_agent = {'User-agent': 'Mozilla/5.0 (X11; Ubuntu;' + 'Linux x86_64; rv:41.0) Gecko/20100101 Firefox/41.0'}
    # get HTML data
    response = requests.get(url, headers=user_agent, auth=('user', 'pass'))
    soup = BeautifulSoup(response.text, html_parser)                        # transform HTML into object tree

    return soup


def main():
    print('*********************\nGoogle Scholar Scraper')
    print('Old Dominion University\nWeb Science and Digital Libraries Group')
    print('Erik Jensen  ejens005@odu.edu')
    print('October 26, 2015')
    print('*********************')

    if sys.argv[1] and os.path.isfile(sys.argv[1]):                         # check if 2nd CLP is file or author
        group = True                                                        # if file, author set is group
    else:
        group = False                                                       # single author

    max_hits = 10                                                           # default maximum list size
    by_citations = True                                                     # search by number of citations
    by_year = True                                                          # search by year
    citations_size, year_size = max_hits, max_hits                          # delineate list sizes
    first_year = 1900                                                       # search from starting year
    author_name = ''

    index = 0
    for cl_parameter in sys.argv:                                           # parse command line parameters
        if cl_parameter.lower() == 'bycitations':
            by_year = False                                                 # make only 1 list, sorted by citations
            print('Will search by number of citations ONLY.')
        elif cl_parameter.lower() == 'byyear':
            by_citations = False                                            # make only 1 list, sorted by year
            print('Will search by year ONLY.')
        elif cl_parameter.lower() == 'start':
            first_year = int(sys.argv[index + 1])                           # set lower year boundary
            print('Will exclude papers dated before ' +
                  str(first_year) + '.')
        elif cl_parameter.lower() == 'max':
            citations_size = int(sys.argv[index + 1])                       # set maximum citations list size
            year_size = int(sys.argv[index + 1])                            # set maximum year list size
            print('Will return a maximum of ' + sys.argv[index + 1] +
                  ' papers per search.')
        elif not os.path.isfile(cl_parameter):
            match_string = ''
            for i in range(1, 21):
                match_string += str(i)
            if cl_parameter not in match_string:
                author_name += cl_parameter + ' '
        index += 1

    author_name = author_name.strip()                                       # remove trailing whitespace

    if by_citations and not by_year:
        year_size = 0                                                       # only search by citations
    if by_year and not by_citations:
        citations_size = 0                                                  # only search by year

    # # *** read in faculty info ***
    faculty = []
    with open('faculty_info.txt', 'r') as faculty_file:
        for member in faculty_file:
            fields = member.split(',')                                      # split line into fields
            # assign fields
            name, cs_url, gs_url = fields[0].strip(), fields[1].strip(), fields[2].strip()
            faculty.append(FacultyMember(name, cs_url, gs_url))             # add faculty member to set

    # # *** set of authors ***
    if group:                                                               # if reading group of authors from file
        # make Group object using file info
        author_set = Group(citations_size, year_size, group, first_year, faculty)

        # # *** randomly scrape ***
        author_set.scrape_authors()                                         # scrape author and paper info from GS

        # # *** merge author data ***
        if by_citations:
            author_set.compile_citations_set()                              # find most cited papers in group
        if by_year:
            author_set.compile_year_set()                                   # find newest papers in group

        # # *** write to file ***
        author_set.write_group()                                            # write group info to HTML file

    # # *** single author ***
    else:  # if single author
        member = get_faculty_member(author_name, faculty)                   # get faculty member from list

        # open HTML file for writing
        out_file = open(member.name.replace(' ', '_').strip() + '.html', 'w')
        # begin HTML
        out_file.write('<!DOCTYPE html>' + '\n<html>' + '\n<body>' +
                       '\n\n<h1>Old Dominion University</h1>' +
                       '\n<h1>Department of Computer Science</h1>' +
                       '\n<h1>Faculty Google Scholar Page Data</h1>' + '\n')

        author = Author(member.name, member.cs_url, member.gs_url, citations_size, year_size,
                        first_year, [], group, faculty, out_file)           # make Author object
        author.scrape_author()                                              # scrape author and paper info from GS
        author.write_author()                                               # write author info to HTML file

        out_file.write('\n</body>' + '\n</html>')                           # end HTML
        out_file.close()                                                    # close file


if __name__ == "__main__":                                                  # if running this module as main program
    sys.exit(main())                                                        # exit after running main()
