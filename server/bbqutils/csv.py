import csv
import json
from collections import OrderedDict

def csv_file_to_json(csvf):
	out = []
	for line in csv.reader(csvf):
		out.append(line)
	return csv_list_to_json(out)

def csv_list_to_json(rows):
	return json.dumps(csv_list_to_dict(rows))

def csv_list_to_dict(rows):
	out = []
	header = rows.pop(0)
	for row in rows:
		o = OrderedDict()
		for n, h in enumerate(header):
			o[h] = row[n]
		out.append(o)
	return out
