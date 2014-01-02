#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=E1102

'''
Created on 21.07.2011

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

@author: David Kiliani <mail@davidkiliani.de>
'''

import re
import mechanize
import subprocess
import sys
import codecs
from pybtex.database.input import bibtex
import os
DOI_REGEX = "doi.+(10\\.\d{4,6}/[^\"'&<% \t\n\r\f\v]+)"


browser = mechanize.Browser()
browser.set_handle_robots(False)
browser.addheaders = [('User-agent', 'Firefox')] 
    
    
def insert_doi(file_str, key, doi):
    return file_str.replace(key + ",\n", key + ",\n  doi = {" + doi + "},\n")

def detex(tex_str):
    '''
    Remove any tex markup from the string. This calls the external
    program detex.
    @param tex_str: the string to be cleaned.
    '''
    prog = subprocess.Popen(["detex"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    return prog.communicate(tex_str)[0]

def fuzzy_match(orig, sub):
    '''
    Do a fuzzy match of two strings. Returns the amount of word pairs
    in the substring that also appear in the original string.
    @param orig: the original string to be searched.
    @param sub: the substring to look for in orig.
    '''
    orig = re.sub(r'[^a-zA-Z0-9 ]+', '', orig)
    sub = re.sub(r'[^a-zA-Z0-9 ]+', '', sub)
    sub = sub.lower().split()
    pairs = [" ".join(sub[i:i+2]) for i in range(len(sub) - 1)]
    match = [len(p) for p in pairs if p in orig.lower()]
    return float(sum(match))/len("".join(pairs))

def find_doi(sourcecode):
    '''
    Look for a Digital Object Identifier (DOI) in the sourcecode
    of an HTML page.
    @param sourcecode: the sourcecode as a string.
    '''
    return re.findall(DOI_REGEX, sourcecode, re.I)[0]

def crossref_abstract_to_doi(abstract):
    browser.open("http://www.crossref.org/guestquery/")
    assert browser.viewing_html()
    browser.select_form(name="form3")
    browser["reference"] = abstract
    response = browser.submit()
    sourcecode = response.get_data()
    try:
        return find_doi(sourcecode)
    except:
        pass
def crossref_auth_title_to_doi(author, title):
    browser.open("http://www.crossref.org/guestquery/")
    assert browser.viewing_html()
    browser.select_form(name="form2")
    # use only surname of first author
    browser["auth2"] = re.sub(r'[A-Z] ', ' ',
        re.sub(r'[^a-zA-Z0-9 ]+', ' ', author).split("and")[0])
    browser["atitle2"] = re.sub(r'[^a-zA-Z0-9 ]+', ' ', title)
    try: #I moved this        
        response = browser.submit()
        sourcecode = response.get_data()
    
        return find_doi(sourcecode)
    except:
        pass
def google_title_to_doi(title):
    browser.open("http://scholar.google.com/")
    assert browser.viewing_html()
    browser.select_form(name="f")
    browser["q"] = 'intitle:"{0}"'.format(title.strip())
    response = browser.submit()
    browser.follow_link(text=title.strip())
    sourcecode = browser.response().get_data()
    try:
        return find_doi(sourcecode)
    except:
        pass
def google_doi(journal, volume, page, title):
    # use only the first 3 words of the title
    title_s = " ".join(title.split()[:3])
    browser.open("http://www.google.de/search?q={0} {1} {2} {3}".format(
        journal, volume, page, title_s).replace(" ", "%20"))
    assert browser.viewing_html()
    try:
        browser.follow_link(text_regex=r"(?i)^" + title_s + ".*")
        sourcecode = browser.response().get_data()
        return find_doi(sourcecode)
    except:
        pass
def google_aip_doi(volume, page):
    browser.open("http://www.google.de/search?q=site:aip.org+{0}+{1}".format(
        volume, page))
    assert browser.viewing_html()
    try:
        browser.follow_link(url_regex=r"http://\w+.aip.org")
        sourcecode = browser.response().get_data()
        return find_doi(sourcecode)
    except:
        pass
def doi_lookup(doi):
    '''
    Look up a DOI and return the title of the web page.
    @param doi: the DOI to lookup.
    '''
    try:
        browser.open("http://dx.doi.org/{0}".format(doi))
        return browser.title()
    except:
        return ""
    
def bibfile_process(bibfile_name):
    parser = bibtex.Parser()
    bib_data = parser.parse_file(bibfile_name)
    bib_sorted = sorted(bib_data.entries.items(), key=lambda x: x[0])
    bib_sorted = [x for x in bib_sorted if not 'doi' in x[1].fields]
    bibfile = codecs.open(bibfile_name, 'r', encoding='utf-8')
    file_str = unicode().join(bibfile.readlines())
    bibfile.close()
        
    for key, value in bib_sorted[:]:
        try:
            author = detex(value.fields['author'])
            title = detex(value.fields['title'])
            journal = value.fields['journaltitle']
            volume = value.fields['volume']
            pages = value.fields['pages']
        except:
            continue
        doi = crossref_auth_title_to_doi(author, title)
        if not doi:
            if ("Appl. Phys. Lett." == journal) or ("J. Appl. Phys." == journal):
                doi = google_aip_doi(volume, pages)
        if not doi:
            doi = google_doi(journal, volume, pages, title)
        if doi:
            lookup = doi_lookup(doi)
            print "{0:40s}{1}".format(key, doi)
            print title
            print lookup
            print fuzzy_match(lookup, title)
            if (fuzzy_match(lookup, title) >= 0.9):
                file_str = insert_doi(file_str, key, doi)
            else:
                print "Set this DOI?"
                resp = raw_input()
                if resp[0] == 'y':
                    file_str = insert_doi(file_str, key, doi)
                elif re.match(DOI_REGEX, resp, re.I):
                    print "using DOI " + resp
                    file_str = insert_doi(file_str, key, resp)
            bibfile = codecs.open(bibfile_name + ".out", 'w', encoding='utf-8')
            bibfile.write(file_str)
            bibfile.close()

if __name__ == '__main__':
    browser = mechanize.Browser()
    browser.set_handle_robots(False)
    browser.addheaders = [('User-agent', 'Firefox')]         # Google doesn't like robots :/
    bib= raw_input("file:")
    bibfile = "%s/%s" % ( os.getcwd(),bib) if not os.path.isfile(bib) else bib 
    bibfile_process(bibfile)