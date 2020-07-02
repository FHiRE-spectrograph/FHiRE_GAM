import os

def read_region(filepath):
	# save the current regions to a regions file
	os.system('xpaset -p ds9 regions save '+filepath)
	# open that same regions file to read each line and find the guidebox info
	rfile = open(filepath, 'r')
	dimensions=None
	for line in rfile:
		if line.split('(')[0] == 'box':
			boxline = line.split('(')[1].split(')')[0]
			dimensions = boxline.split(',')
			for i in range(len(dimensions)):
				dimensions[i] = int(float(dimensions[i]))
			dimensions = dimensions[:4]
			break
	rfile.close()
	# return the dimensions of the guidebox: [xcenter, ycenter, width, height]
	return dimensions

#print read_region('/d/users/lia/Desktop/regions1.reg')
