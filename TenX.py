from bs4 import BeautifulSoup
import requests
from urllib.request import urlretrieve
from datetime import datetime as dt
import os, re
from pathlib import Path
import glob
from os.path import basename

data_format = '10-k'
DOMIN = 'https://www.sec.gov'

class TenXDownloader:
    def __init__(self, cik, start_date, end_date):
        # define cik type: str or list
        if type(cik) == str:
            cik = [cik]
        elif type(cik) == list:
            for i, ele in enumerate(cik):
                assert type(ele)==str, f'cik at index {i} is not string: %s'%type(ele)
        else:
            raise TypeError('CIK should be string or list of string, input type is %s'%type(cik))

        self.CIK = cik
        self.start_date = dt.strptime(start_date,'%Y%m%d')
        self.end_date = dt.strptime(end_date,'%Y%m%d')
        self.all_url = {}
        self.cwd = os.getcwd()

    def download(self,  reset_flag=False, target = './data', data_format= '10-k'):
        # change current directory
        os.chdir(self.cwd)
        os.chdir(target)
        # search each ticker
        for c in self.CIK:
            try:
                if reset_flag:
                    result = self._search_each(c, data_format)
                else:
                    if c in self.all_url:
                        continue
                    else:
                        result = self._search_each(c, data_format)
            except ValueError as info:
                print(info)
                continue
            
            # make company folder
            try:
                os.mkdir(c)
            except FileExistsError:
                pass
            # change current directory to company folder
            os.chdir(f'./{c}')
            # download html files
            for each in result:
                print(f'Downloading {c}:{each[0]} {each[1]}')
                filename = each[0]+'.htm'#str(each[each[1].rfind('.'):])
                #print('This is test filename: ', each[0],str(each[each[1].rfind('.'):]))
                urlretrieve(each[1], filename)
                print('File saved in {}'.format(os.getcwd()+'\\'+filename))
            # add url to dictionary
            self.all_url[c] = result
            # go back to upper directory
            os.chdir('..')
        os.chdir('..')

    def _search_each(self, cik, data_format):
        """search urls given company cik
        data_format: '10-k' or '10-q'
        """
        assert cik in self.CIK, '%s is not in CIK list'%cik
        # url for the list of htms
        url = f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={data_format}&dateb=&owner=exclude&count=40'
        search_page = requests.get(url)

        # check if the request is successful
        assert search_page.status_code == 200, 'request code for search page: %s' % search_page.status_code

        search_head = BeautifulSoup(search_page.content, 'html.parser')
        search_result = search_head.select('table.tableFile2 tr')
        if len(search_result)==0:
            raise ValueError(f'Result for {cik} is not available, {url}')
        search_result.pop(0)
        start_idx, end_idx = self._search_date([self._get(item, 'date') for item in search_result], self.start_date, self.end_date)
        
        
        result = []
        for i in range(start_idx, end_idx+1):
            # if form type is not '10-K'/'10-Q'
            if self._get(search_result[i], 'type')!= data_format.upper():
                continue
            date = self._get(search_result[i], 'date').strftime('%Y%m%d')
            sub_url = DOMIN + search_result[i].find('a', attrs={"id": "documentsbutton"})['href']

            company_page = requests.get(sub_url)
            assert  company_page.status_code == 200, 'request code for company page: %s' % company_page.status_code
            company_head = BeautifulSoup(company_page.content, 'html.parser')
            file_table = company_head.select('table.tableFile')[0].select('tr')
            file_table.pop(0)

            for item in file_table:
                if data_format.upper() in item.select('td')[3].contents[0]:
                    break
            doc_url = item.select('td a')[0]['href']
            result.append((date, DOMIN+doc_url))
        return result

    def _get(self, item, info):
        if info == 'date':
            date = item.select('td')[3].contents[0]
            ret = dt.strptime(date,'%Y-%m-%d')
        elif info == 'url':
            ret = DOMIN + item.find('a', attrs={"id": "documentsbutton"})['href']
        elif info == 'type':
            ret = item.select('td')[0].contents[0]
        else:
            raise NotImplementedError
        return ret

    def _search_date(self, ls, start, end):
        h, t = ls[-1], ls[0]
        n = len(ls)
        assert start <= t and end >= h, f'Available time interval: {h} to {t}, input: {start} to {end}'
        # print(h,t)
        if start >= h:
            ei, _ = self._bsearch_dec(ls, start)
        else:
            ei = len(ls)-1
        if end <= t:
            _, si = self._bsearch_dec(ls, end)
        else:
            si = 0
        return si, ei

    def _bsearch_dec(self, ls, point):
        a = 0
        b = len(ls)
        while b-a > 1:
            tmp = int((a+b)/2)
            if ls[tmp] >= point:
                a = tmp
            else:
                b = tmp
        return a,b

class TenXScraper:
    def __init__(self, section, next_section, form_type):
        self.all_section = [str(i) for i in range(1, 16)] + ['1A', '1B', '7A', '9A', '9B']
        section = re.findall(r'\d.*\w*', section.upper())[0]
        next_section = re.findall(r'\d.*\w*', next_section.upper())[0]
        if section  not in self.all_section:
            raise ValueError(f'Section: {section} is not avaiable, avaiable section: {self.all_section}')
        if next_section  not in self.all_section:
            raise ValueError(f'Section: {next_section} is not avaiable, avaiable section: {self.all_section}')
        self.section = 'Item ' + section
        self.next_section = 'Item ' + next_section
        self.form_type = form_type

    def scrape(self, input_path, output_path):
        """filter for ITEM 1A and then parse
        """
        with open(input_path, 'rb') as input_file:
            page = input_file.read()  # <===Read the HTML file into Python
            
            # Pre-processing the html content by removing extra white space and combining then into one line.
            page = page.strip()  # <=== remove white space at the beginning and end
            page = page.replace(b'\n', b' ')  # <===replace the \n (new line) character with space
            page = page.replace(b'\r', b'')  # <===replace the \r (carriage returns -if you're on windows) with space
            page = page.replace(b'&nbsp;', b' ')  # <===replace "&nbsp;" (a special character for space in HTML) with space.
            page = page.replace(b'&#160;',b' ')  # <===replace "&#160;" (a special character for space in HTML) with space.
            while b'  ' in page:
                page = page.replace(b'  ', b' ')  # <===remove extra space

            # Using regular expression to extract texts that match a pattern
            # Define pattern for regular expression.
            # The following patterns find ITEM 1 and ITEM 1A as diplayed as subtitles
            # (.+?) represents everything between the two subtitles
            # If you want to extract something else, here is what you should change

            # Define a list of potential patterns to find ITEM 1 and ITEM 1A as subtitles
            p1 = bytes(r'bold;\">\s*' + self.section + r'\.(.+?)bold;\">\s*' + self.next_section + r'\.',
                       encoding='utf-8')
            p2 = bytes(r'b>\s*' + self.section + r'\.(.+?)b>\s*' + self.next_section + r'\.', encoding='utf-8')
            p3 = bytes(r'' + self.section + r'\.\s*<\/b>(.+?)' + self.next_section + r'\.\s*<\/b>', encoding='utf-8')
            p4 = bytes(r'' + self.section + r'\.\s*[^<>]+\.\s*<\/b(.+?)' + self.next_section + r'\.\s*[^<>]+\.\s*<\/b',
                       encoding='utf-8')
            p5 = bytes(r'b>\s*<font[^>]+>\s*' + self.section + r'\.(.+?)b>\s*<font[^>]+>\s*' + self.next_section + r'\.', encoding='utf-8')
            p6 = bytes(r'' + self.section.upper() + r'\.\s*<\/b>(.+?)' + self.next_section.upper() + r'\.\s*<\/b>', encoding='utf-8')

            p7 = bytes(r'underline;\">\s*' + self.section + r'\<\/font>(.+?)underline;\">\s*'+ self.next_section + r'\.\s*\<\/font>',encoding = 'utf-8')
            p8 = bytes(r'underline;\">\s*' + self.section + r'\.\<\/font>(.+?)underline;\">\s*'+ self.next_section + r'\.\s*\<\/font>',encoding = 'utf-8')
            p9 = bytes(r'<font[^>]+>\s*' + self.section + r'\:(.+?)\<font[^>]+>\s*'+self.next_section + r'\:\s*',encoding = 'utf-8')
            p10 = bytes(r'<font[^>]+>\s*' + self.section + r'\.\<\/font>(.+?)\<font[^>]+>\s*' + self.next_section + r'\.',encoding = 'utf-8')
            p11 = bytes(r'' + self.section + r'\.(.+?)<font[^>]+>\s*' + self.next_section + r'\.\<\/font>',encoding = 'utf-8')
            p12 = bytes(r'b>\s*<font[^>]+>\s*' + self.section + r'(.+?)b>\s*<font[^>]+>\s*' + self.next_section + r'\s*\<\/font>', encoding='utf-8')
            p13 = bytes(r'' + self.section + r'\.\s*[^<>]+\.\s*<\/b(.+?)b>\s*' + self.next_section + r'\.',
                       encoding='utf-8')
            p14 = bytes(r'\<\/A>' + self.section + r'\.(.*?)' + self.next_section + r'\.\<\/B>\<\/FONT>\<\/TD>\s*',encoding = 'utf-8')
            p15 = bytes(r'\<\/A>\s*' + self.section + r'\.(.*?)\<\/A>\s*'+ self.next_section+ r'\.' ,encoding = 'utf-8')
            p16 = bytes(self.section + r'\.\<\/font>\<font style="font-family:inherit;font-size:10pt;font-weight:bold;">(.*)?'+ self.next_section+ r'\.\<\/font>' ,encoding = 'utf-8')
            p17 = bytes(self.section + r'\.\s*\<\/font>\<font style="font-family:Franklin Gothic Medium,sans-serif;font-size:10pt;color:#002f6c;font-weight:bold;">(.*)?'+ self.next_section+ r'\.\<\/font>' ,encoding = 'utf-8')
            p18 = bytes(self.section + r'\.\<font id="TAB2" style="LETTER-SPACING: 9pt">\s*\<\/font>\s*(.*?)'+ self.next_section ,encoding = 'utf-8')
            p19 = bytes(r'\<\/B>\<\/FONT>\<FONT SIZE=2>'+self.section + r'(.*?)\<\/B>\<\/FONT>\<FONT SIZE=2>'+ self.next_section ,encoding = 'utf-8')
            p20 = bytes(r'\<strong>'+self.section + r'(.*?)\<strong>'+ self.next_section ,encoding = 'utf-8')
            p21 = bytes(self.section + r'\.\s*\<font style="DISPLAY: inline; FONT-STYLE: italic">(.*?)'+ self.next_section ,encoding = 'utf-8')
            p22 = bytes(r'I\<A NAME="c68209a010_v3">\<\/A>tem 1A\.' + r'(.*?)'+ r'I\<A NAME="c68209a012_v3">\<\/A>tem 1B\.' ,encoding = 'utf-8')
            p23 = bytes(r';">'+self.section + r'\.\s+(.*?)'+ self.next_section + r'\.\s+' ,encoding = 'utf-8')
            p24 = bytes(r'\<\/A>'+self.section + r'\.\<\/B>\<\/FONT>\<\/TD>\s+(.*?)\<\/A>'+ self.next_section + r'\.\s+' ,encoding = 'utf-8')
            p25 = bytes(r'[\<a name="ITEM_1A">|\<a name="ITEM1ARISKFACTORS">]'+self.section + r'\.\s+(.*?)'+ self.next_section + r'\.\s+' ,encoding = 'utf-8')
            p26 = bytes(self.section + r':\s+\<\/FONT>\s+\<\/TD>\s+\<TD>\s+\<FONT style="font-family: \'Times New Roman\', Times">(.*?)\s+\<TD>\s+\<FONT style="font-family: \'Times New Roman\', Times">' ,encoding = 'utf-8')
            p27 = bytes( r'\<B>\<I>'+self.section+r'\.\<\/I>\<\/B>(.*?)\<B>\<I>'+self.next_section ,encoding = 'utf-8')
            p28 = bytes(r'\<font style="DISPLAY: inline; FONT-WEIGHT: bold">'+self.section+r'\.\s+(.*?)\<font style="DISPLAY: inline; FONT-WEIGHT: bold">'+self.next_section ,encoding = 'utf-8')
            p29 = bytes(r'\<FONT face="serif">'+self.section+r'\.\s+(.*?)\<FONT face="serif">'+self.next_section ,encoding = 'utf-8')
            p30 = bytes(self.section[1:]+r'\.\<\/B>\<\/FONT>\<\/TD>\s+(.*?)'+self.next_section+r'\.\<\/B>\<\/FONT>\<\/TD>\s+' ,encoding = 'utf-8')
            p31 = bytes(r'TEM \<\/SMALL>1A\<\/B>'+r'(.*?)'+r'I\<SMALL>TEM\s+\<\/SMALL>1',encoding = 'utf-8')
            p32 = bytes(self.section + r'\<\/font>\<a name="RISK_FACTORS">\<\/a>'+r'(.*?)'+ self.next_section +r'\<\/font>\<a name="UNRESOLVED_STAFF_COMMENTS">',encoding = 'utf-8')
            p33 = bytes(r'\<strong>\<a name="Item1A">'+self.section + r'\.\<\/a>\<\/strong>(.*?)\<strong>'+ self.next_section + r'\<\/strong>',encoding = 'utf-8')
            p34 = bytes(r'\<a name="Item1A">'+self.section + r'\.\<\/a>\<\/font>\<\/div>(.*?)\<a name="Item1B">'+ self.next_section + r'\.\<\/a>\<\/font>\<\/div>',encoding = 'utf-8')
            p35 = bytes(self.section + r'\.\<\/font>\<\/div> \<\/td> \<td width="923"> (.*?)'+ self.next_section + r'\.\<\/font>\<\/div> \<\/td> ',encoding = 'utf-8')
            p36 = bytes(self.section + r'\.\<\/font>\<\/div>\<\/td>\<td style="vertical-align:top;">(.*?)'+ self.next_section + r'\.\<\/font>\<\/div>\<\/td>\<td style="vertical-align:top;">',encoding = 'utf-8')
            p37 = bytes(r'Ite\<A NAME="Item1A">\<\/A>m 1A\.(.*?)Item 1\<A NAME="Item1B">\<\/A>B\.',encoding = 'utf-8')
            p38 = bytes(r'\<\/A>'+self.section +r':\<\/B>\<B>\<I>(.*?)\<\/A>'+ self.next_section + r':\s*\<\/B>\<B>\<I>',encoding = 'utf-8')
            p39 = bytes(r'\<\/A>'+self.section +r':\s*\<\/B>(.*?)\<\/A>'+ self.next_section + r':\s*\<\/B>',encoding = 'utf-8')
            p40 = bytes(self.section+ r'\.\s+(.*?)'+ self.next_section+r'\.\s*',encoding = 'utf-8')
            p41 = bytes(self.section+ r'\.\<\/font>\<\/div>\<\/td>(.*?)'+ r'Item\s*1B'+r'\.\<\/font>\<\/div>\<\/td>',encoding = 'utf-8')
            p42 = bytes(r'Item 1\(a\)'+ r'\.\<\/font>\<font style="font-family:inherit;font-size:10pt;font-weight:bold;">(.*?)'+ r'Item 1\(b\)'+r'\.\<\/font>\<font style="font-family:inherit;font-size:10pt;font-weight:bold;">',encoding = 'utf-8')
            p43 = bytes(r'\<TD>\<B>'+self.section + r'\.\<\/B>\<\/TD>(.*?)\<TD>\<B>'+ r'Item 3'+r'\.\<\/B>\<\/TD>',encoding = 'utf-8')
            p44 = bytes(self.section + r'\.\<I>(.*?)'+ r'Item 3'+r'\.\<I>\s+\<\/I>\<\/FONT>\<\/B>',encoding = 'utf-8')
            p45 = bytes(r'\<\/A>'+self.section + r'\.(.*?)\<\/A>'+ r'Item 3'+r'\.',encoding = 'utf-8')
            p46 = bytes( r'Item \<a name="1a">1A\.\<\/a>'+ r'(.*?)'+ r'Item \<a name="1b">1B\.\<\/a>',encoding = 'utf-8')
            p47 = bytes( self.section+r'\.\<\/font>\<\/div> \<\/td> \<td align="left">'+ r'(.*?)'+ r'Item1B\. \<\/font>',encoding = 'utf-8')
            p48 = bytes( self.section+r'\. Risk Factors\<\/font>\<\/div>'+ r'(.*?)'+ r'Item1B\. \<\/font>',encoding = 'utf-8')
            p49 = bytes( scraper.section+r'\.\<\/a>'+ r'(.*?)'+scraper.next_section + r'\.\<\/a>',encoding = 'utf-8')
            p50 = bytes( r'I\<\/B>\<\/FONT>\<FONT FACE="TIMES NEW ROMAN" COLOR="#00009D" STYLE="FONT-SIZE:10PT">\<B>TEM\<\/B>\<\/FONT> \<FONT FACE="TIMES NEW ROMAN" COLOR="#00009D" STYLE="FONT-SIZE:12PT">\<B>1A'+ r'(.*?)'+r'I\<\/B>\<\/FONT>\<FONT FACE="TIMES NEW ROMAN" COLOR="#00009D" STYLE="FONT-SIZE:10PT">\<B>TEM\<\/B>\<\/FONT> \<FONT FACE="TIMES NEW ROMAN" COLOR="#00009D" STYLE="FONT-SIZE:12PT">\<B>3',encoding = 'utf-8')
            p51 = bytes( r'\<b>ITEM 1A RISK FACTORS\<\/b>\<\/font>\<\/p>'+ r'(.*?)'+r'\<b>ITEM 1B UNRESOLVED STAFF COMMENTS\<\/b>\<\/font>\<\/p>',encoding = 'utf-8')
            p52 = bytes( self.section+ r'\<\/font>\<\/font>\<\/td>(.*?)'+self.next_section+r'\<\/font>\<\/font>\<\/td>',encoding = 'utf-8')
            p53 = bytes( self.section+ r' RISK FACTORS (.*?)'+self.next_section,encoding = 'utf-8')
            p54 = bytes( self.section+ r'\<\/font>\<\/div> \<\/td> \<td valign="top" width="90%">(.*?)'+self.next_section+r'\<\/font>\<\/div>',encoding = 'utf-8')

            regexs = (
                p1,  # <===pattern 1: with an attribute bold before the item subtitle
                p2,  # <===pattern 2: with a tag <b> before the item subtitle
                p3,  # <===pattern 3: with a tag <\b> after the item subtitle
                p4,  # <===pattern 4: with a tag <\b> after the item+description subtitle
                p5,  # <===pattern 5: with a tag <b><font ...> before the item subtitle
                p6,  # <===pattern 6: with a tag <\b> after the item subtitle (ITEM XX.<\b>)
                p7,
                p8,
                p9,
                p10,
                p11,
                p12,
                p13,
                p14,
                p15,
                p16, # for ALGN
                p17,  # for ALXN
                p18,     # for BSX healthcare
                p19,     # for CI
                p20,     # strong!! for CNC
                p21,     # CNC
                p22,     # DGX 2012
                p23,    # DGX rest
                p24,     # DHR
                p25,     # HSIC
                p26,    # LLY
                p27,     # LLY
                p28,
                p29,     # PFE
                p30,     # PFE 2009
                p31,     # RMD 2007 + 
                p32,     # RMD 2018 +
                p33,     # TMO 2006
                p34,     # TMO 2008
                p35,     # TMO
                p36,     # TMO
                p37,     # VAR 2013
                p38,     # WAT 2012
                p39,     # WAT 2014
                p40,
                p41,     # Energy CVX
                p42,     # Energy HAL
                p43,    # HES
                p44,
                p45,
                p46,
                p47,
                p48,
                p49,
                p50,    # OXY
                p51,    # OXY
                p52,
                p53,    # OXY
                p54     # OXY
                ) 

            # Now we try to see if a match can be found...
            for idx, regex in enumerate(regexs):
                match = re.search(regex, page,
                                  flags=re.IGNORECASE)  # <===search for the pattern in HTML using re.search from the re package. Ignore cases.

                # If a match exist....
                if match:
                    print('Matched: ',idx+1)
                    # Now we have the extracted content still in an HTML format
                    # We now turn it into a beautiful soup object
                    # so that we can remove the html tags and only keep the texts

                    soup = BeautifulSoup(match.group(1),
                                         "html.parser")  # <=== match.group(1) returns the texts inside the parentheses (.*?)

                    # soup.text removes the html tags and only keep the texts
                    rawText = soup.text.encode('utf8')  # <=== you have to change the encoding the unicodes

                    # remove space at the beginning and end and the subtitle "business" at the beginning
                    # ^ matches the beginning of the text
                    # outText = re.sub(b"^business\s*", b"", rawText.strip(), flags=re.IGNORECASE)
                    Path(output_path).touch()
                    with open(output_path, "wb") as output_file:
                        output_file.write(rawText)
                    if len(rawText) >= 1000:
                        break  # <=== if a match with text length > 1000 is found, we break the for loop. Otherwise the for loop continues

        if match is None or len(rawText) < 20:
            print(f'No matched sections: {self.section}, {self.next_section} found in {input_path}.')
            return None
        else:
            return rawText

    def scrape_method2(self, input_path, output_path):
        """Parse the page and then filter for ITEM 1A Risk Factor
        """
        with open(input_path, 'rb') as input_file:
            page = input_file.read()  # <===Read the HTML file into Python
            
            # Pre-processing the html content by removing extra white space and combining then into one line.
            page = page.strip()  # <=== remove white space at the beginning and end
            page = page.replace(b'\n', b' ')  # <===replace the \n (new line) character with space
            page = page.replace(b'\r', b' ')  # <===replace the \r (carriage returns -if you're on windows) with space
            page = page.replace(b'&nbsp;', b' ')  # <===replace "&nbsp;" (a special character for space in HTML) with space.
            page = page.replace(b'&#160;',b' ')  # <===replace "&#160;" (a special character for space in HTML) with space.
            while b'  ' in page:
                page = page.replace(b'  ', b' ')  # <===remove extra space
            
            # Parse the page, remove all HTML tags
            soup = BeautifulSoup(page, "html.parser")
            
            # general case
            if self.form_type == '10-k':
                pattern = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:|\—|\-|\–]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*1\s*[\(|\s]?B\)?\s*[\.|\/|:|\—|\-|\–]?\s*UNRESOLVED (Securities and Exchange Commission |SEC )?STAFF\s+COMMENTS?\.?)', re.IGNORECASE)
            if self.form_type == '10-q':
                pattern = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*2\s*[\.|\/|:]?\s*UNREGISTERED SALE[S]? OF EQUITY SECURITIES AND USE OF PROCEEDS\.?)', re.IGNORECASE)

            # special cases
            if self.form_type == '10-k':
                pattern_1 = re.compile(r'(ITEM\s1A\s*[\.|\/]?\s+RISK FACTORS)(.*?)(ITEM\s1B\s*[\.|\/]?\s*UNRESOLVED (SEC )?STAFF COMMENTS)') # for RRC 
                pattern_2 = re.compile(r'(RISK FACTORS\s*)(Risk Factors|Our financial results)(.*?)(ITEM\s1B\s*[\.|\/]?\s*UNRESOLVED (SEC )?STAFF COMMENTS)', re.IGNORECASE)
                pattern_3 = re.compile(r'(Certain Risks\s*)(.*?)((ITEM\s2)|(ITEM\s1B\s*[\.|\/]?\s*UNRESOLVED (SEC )?STAFF COMMENTS))', re.IGNORECASE)
                pattern_4 = re.compile(r'(ITEM\s1\(?A\)?\s*[\.|\/]?\s*Risk Factors Related to Our Business and Operations\.?\s*)(Our business activities and the value of our securities are subject to significant risk factors)(.*?)(ITEM\s*3\s*[\.|\/]?\s*Legal Proceedings\.?)', re.IGNORECASE)
                pattern_5 = re.compile(r'(ITEM\s1\(?A\)?\s*[\.|\/]?\s*Risk Factors\.?)(.*?)(ITEM\s*3\s*[\.|\/]?\s*Legal Proceedings\.?)', re.IGNORECASE)
                pattern_6 = re.compile(r'(ITEM\s1\(?A\)?\s*[\.|\/|:]?\s*RISK FACTORS\.?)(.*?)(ITEM\s*2\s*[\.|\/|:]?\s*PROPERTIES\.?)', re.IGNORECASE)
                pattern_7 = re.compile(r'(RISK FACTORS\s*){2}(.*?)(Properties and Legal Proceedings)', re.IGNORECASE)
                pattern_8 = re.compile(r'(RISK FACTORS\s*)(.*?)(ANALYSIS OF CHANGES IN NET INTEREST INCOME)')
                pattern_9 = re.compile(r'(Risk Factors\s*)(There are a number of factors)(.*?)(ENTRY INTO CERTAIN COVENANTS|CAPITAL COVENANTS)')
                pattern_10 = re.compile(r'(RISKS\s*Risk Factors Relating to Our Business)(.*?)(Risk Management\_+)')
                pattern_11 = re.compile(r'(Risk Factors\s*)(For a discussion of the risks and uncertainties)(.*?)(Unresolved Staff Comments)')
                pattern_12 = re.compile(r'(RISK FACTORS\s*)(The following discussion sets forth certain risks)?(.*?)(MANAGING GLOBAL RISK|CAPITAL RESOURCES AND LIQUIDITY\s*)')
                # created a mapping from companies to specific pattern
                pattern_map = {'RRC': pattern_1, 'VLO': pattern_2, 'XEC': pattern_3, 'HES': pattern_4, 'OXY': pattern_5, 'RMD': pattern_6, 'LLY':pattern_6, 
                'LH': pattern_6,'CAH':pattern_7, 'WFC':pattern_8, 'USB': pattern_9, 'SYF':pattern_10, 'MS':pattern_11, 'LNC':pattern_6, 'HIG':pattern_6, 
                'C': pattern_12, 'AJG':pattern_6
                }
            
            if self.form_type == '10-q':
                pattern_1 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*6\s*[\.|\/|:]?\s*EXHIBITS\.?)', re.IGNORECASE)
                pattern_6 = re.compile(r'(RISK\s*FACTORS\s+\(ITEM\s*1A\)\s)(.*?)(Exhibits\s+\(ITEM\s*6\)\s*)', re.IGNORECASE)

                pattern_2 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*4\s*[\.|\/|:]?\s*Mine Safety Disclosures\.?)', re.IGNORECASE)
                
                pattern_3 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(\s*In addition to the other information set forth in this Report)(.*?)(ITEM\s*2\s*[\.|\/|:]?\s*UNREGISTERED SALES OF EQUITY SECURITIES AND USE OF PROCEEDS\.?)', re.IGNORECASE)
                pattern_5 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(.*?)(ITEM\s*2\s*[\.|\/|:]?\s*UNREGISTERED SALES OF EQUITY SECURITIES\s*(AND (THE)? USE OF PROCEEDS)?\.?\,?)', re.IGNORECASE)
                pattern_8 = re.compile(r'(ITEM\s*1A\s*[\—|\—|\-]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*2\s*[\—|\—|\-|\-]?\s*Unregistered Sales of (Equity )?Securities and Use of Proceeds)', re.IGNORECASE)

                pattern_4 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s*RISK\s*FACTORS\.?)(.*?)(ITEM\s*4\s*[\.|\/|:]?\s*Submission of Matters to (a\s*)?Vote of Security Holders\.?)', re.IGNORECASE)
                pattern_7 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(.*?)(ITEM\s*4\s*[\.|\/|:]?\s*Submission of Matters to a Vote of Security Holders\.?)', re.IGNORECASE)

                pattern_9 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(.*?)(ITEM\s*2\s*[\.|\/|:]?\s*ISSUER PURCHASE(S)? OF EQUITY SECURITIES)', re.IGNORECASE)
                pattern_10 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(.*?)(ITEM\s*5\s*[\.|\/|:]?\s*Other Information)', re.IGNORECASE)
                pattern_11 = re.compile(r'(ITEM\s*1\(?A\)?\s*[\.|\/|:]?\s+RISK\s*FACTORS\.?)(.*?)(ITEM\s*4\s*[\.|\/|:]?\s*Mine Safety Disclosures.)', re.IGNORECASE)


                pattern_map = {'COP': pattern_1, 'EQT': pattern_1, 'HP': pattern_1, 'MPC': pattern_1, 'NBL': pattern_1, 'NOV': pattern_2, 'PSX': pattern_1, 
                'PXD': pattern_3, 'RRC': pattern_1, 'WMB': pattern_1, 'XEC': pattern_1, 'AIG': pattern_1, 'AIZ': [pattern_1,pattern_4], 'BAC':pattern_5, 
                'FITB': pattern_6, 'HBAN': pattern_1, 'HRB': pattern_5, 'KEY': pattern_4, 'STT': [pattern_4, pattern_1], 'UNM': pattern_1, 'WLTW': pattern_8, 
                'ALXN': pattern_1, 'AMGN': [pattern_5, pattern_1], 'BMY': pattern_9, 'BSX': pattern_1, 'COO': [pattern_1, pattern_10], 'HCA': pattern_1,
                'INCY': pattern_1, 'IQV': pattern_5, 'MDT': pattern_1, 'MYL': pattern_1, 'PRGO': pattern_11, 'REGN': pattern_1, 'TMO': [pattern_1, pattern_4, pattern_8],
                'XRAY': pattern_8
                }
            # add general pattern to pattern_list
            pattern_list = [pattern]
            
            # append patterns if match company names
            company_name = basename(Path(input_path).parent)
            if  company_name in pattern_map:
                if type(pattern_map[company_name]) != list:
                    pattern_list.append(pattern_map[company_name])
                else:
                    pattern_list = pattern_list + pattern_map[company_name]
            
            rawText = None
            for pattern in pattern_list:
                for match in pattern.finditer(soup.text):
                    # write to output file
                    # you have to change the encoding the unicodes
                    rawText = match.group().encode('utf8')
                    # write extracted text to output
                    Path(output_path).touch()
                    with open(output_path, "wb") as output_file:
                        output_file.write(rawText)

                    if len(match.group()) <= 1000:
                        continue
                    else:
                        break
            
        if rawText == None:
            print("Match missing: ", input_path)
        else:
            print("Match found: ",input_path)
        return rawText



if __name__=='__main__':
    # company_name = 'PXD'
    # downloader = TenXDownloader(company_name, '20060101','20191101')
    # downloader.download(company_name,target = './10-q_Energy', data_format='10-q')


    scraper = TenXScraper('Item 1A', 'Item 1B', '10-q')  # scrape text start from Item 1A, and stop by Item 1B
    # #scraper.scrape_method2('./Energy/APA/20150227.htm', './Energy/APA/20150227.txt') # makse sure ./data/txt exists
    company_name = 'XRAY'
    for file in glob.glob('./10-q_Healthcare/'+company_name+'/*.htm'):
        #print(file[-12:-3])
        scraper.scrape_method2(file, './10-q_Healthcare/'+company_name+'/'+file[-12:-3]+'txt') # makse sure ./data/txt exists


    #scraper2 = TenKScraper('Item 7', 'Item 8')
    #print(scraper.self)
    #scraper2.scrape('./data/HSIC/20100223.htm', './data/txt/test2.txt')
# /Users/shelly/Documents/BIA660FinalProject/data/DGX/20140218.htm

# /Users/shelly/Documents/BIA660FinalProject/data/DHR/20120224.htm