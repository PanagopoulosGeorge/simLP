import sys
import os
from os import walk

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../src"))
import run

if __name__=="__main__":
	subfolder_names = [f for f in list(walk(current_dir))[0][1] if f != "__pycache__" and os.path.isdir(os.path.join(current_dir, f))]
	subfolders = [os.path.join(current_dir, subfolder) for subfolder in subfolder_names if subfolder != "test6"]
	for subfolder in sorted(subfolders):
		print("--------------------------------")
		print("Running unit test for: " + subfolder)
		print("--------------------------------")
		matching, distances, similarity, feedback = run.parse_and_compute_distance(subfolder + "/generated.prolog", subfolder + "/ground.prolog", subfolder + "/log.txt", generate_feedback=True)
		print(subfolder)
		print(matching)
		print(distances)
		print(similarity)
		f = open(subfolder + "/results.csv", 'r')
		flag = 0
		i = 0
		mistakesNo = 0
		for line in f:
			my_line = line.strip()
			if len(line)==1:
				i = 0
				flag += 1
			elif flag==0:
				if int(my_line) != matching[i]:
					mistakesNo += 1
					print("Error in the matching of rule " + str(i))
					print("My matching is: " + str(matching[i]))
					print("Correct matching is: " + my_line)
				i+=1
			elif flag==1:
				if float(my_line) != round(distances[i], 4):
					mistakesNo += 1
					print("Error in the distance of rule " + str(i))
					print("My distance is: " + str(round(distances[i], 4)))
					print("Correct distance is: " + my_line)
				i+=1
			elif flag==2:
				if float(my_line) != round(similarity, 4):
					mistakesNo += 1
					print("Incorrect Similarity")
					print("My similarity is: " + str(round(similarity, 4)))
					print("Correct distance is: " + my_line)
				i+=1
		f.close()
		print("Number of incorrect results: " + str(mistakesNo))
		print()
		print()
		


