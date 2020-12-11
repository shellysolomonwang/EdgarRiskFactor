# read & write
sector = 'finance'
total_count = 98
failed_count = 32
with open('./'+'test'+'_rate.txt', 'a') as filehandle:
    filehandle.write(f'sector, total_count, failed_count\n')
    filehandle.write(f'{sector}, {total_count}, {failed_count}\n')

for folder in glob.glob(form_type+'_'+sector + '/*'):
		for filename in glob.glob(folder+'/*.htm'):