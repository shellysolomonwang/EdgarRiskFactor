from TenX import TenXDownloader, TenXScraper
import glob
import os

def scrape(sector, form_type='10-k'):

	# read Ticker names from txt files
	with open(sector +'.txt','r') as f:
		company_name = [line.strip() for line in f]
		print (company_name)

	# create ./data/ folder if not exist
	try:
		os.mkdir('data')
	except:
		pass
	
	# dowload from 2006 to 2019
	downloader = TenXDownloader(company_name, '20060101','20191101')
	downloader.download(data_format=form_type)
	# rename ./data/ folder to ./'sector'/ folder
	# if form_type == '10-k':
	# 	os.rename('data', sector)
	# if form_type == '10-q':
	os.rename('data', form_type+'_'+sector)
	
	total_count = 0
	failed_count = 0
	#failed = [] # to record files failed to scrape
	for folder in glob.glob(form_type+'_'+sector + '/*'):
		for filename in glob.glob(folder+'/*.htm'):
			total_count +=1
			print (f'FILE No.{total_count}', filename)
			scraper = TenXScraper('Item 1A', 'Item 1B', form_type) 
			result = scraper.scrape_method2( filename, filename[:-3] + 'txt')
			
			if result == None:
				print('Scraping failed!')
				failed_count +=1
			# elif len(result) >= 1000:
			# 	os.remove(filename)
			# 	print("File Removed!")
			# else:
			# 	print("File too short!")
	
	print(f'{sector}, {total_count}, {failed_count}\n')
	# append new count result into txt
	with open('./'+form_type+'_rate.txt', 'a') as filehandle:
		filehandle.write(f'{sector}, {total_count}, {failed_count}\n')
	

if __name__ == "__main__":
	# scrape('Energy', form_type='10-q')
	
	scrape('Healthcare', form_type='10-q')
	scrape('Financial', form_type='10-q')

	# os.rename('data', 'data_'+sector)
	#sector = 'data_'+sector
	
	# for folder in glob.glob(sector + '/*'):
	# 	print(folder)
	# 	for filename in glob.glob(folder+'/*.htm'):
	# 		print ('FILE:', filename)
	# 		scraper = TenXScraper('Item 1A', 'Item 1B') 
	# 		scraper.scrape( filename, filename[:-3] + 'txt')
	# 		os.remove(filename)
	# 		print(filename, "File Removed!")

