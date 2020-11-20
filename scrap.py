from TenK import TenKDownloader, TenKScraper
import glob
import os

def scrape(sector):
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
	downloader = TenKDownloader(company_name, '20060101','20191101')
	downloader.download()
	# rename ./data/ folder to ./'sector'/ folder
	os.rename('data', sector)
	
	
	failed = [] # to record files failed to scrape
	for folder in glob.glob(sector + '/*'):
		print(folder)
		for filename in glob.glob(folder+'/*.htm'):
			print ('FILE:', filename)
			# Changed
			scraper = TenKScraper('Item 1A', 'Item 1B') 
			result = scraper.scrape_method2( filename, filename[:-3] + 'txt')
			
			if result == None:
				print(filename, 'failed!')
				failed.append(filename)
			else:
				os.remove(filename)
				print(filename, "File Removed!")
	
	with open('./'+sector+'_failed.txt', 'w') as filehandle:
		for listitem in failed:
			filehandle.write('%s\n' % listitem)

if __name__ == "__main__":
	# scrape('Energy')
	scrape('Financial')
	# scrape('Healthcare')

	# os.rename('data', 'data_'+sector)
	#sector = 'data_'+sector
	
	# for folder in glob.glob(sector + '/*'):
	# 	print(folder)
	# 	for filename in glob.glob(folder+'/*.htm'):
	# 		print ('FILE:', filename)
	# 		scraper = TenKScraper('Item 1A', 'Item 1B') 
	# 		scraper.scrape( filename, filename[:-3] + 'txt')
	# 		os.remove(filename)
	# 		print(filename, "File Removed!")

