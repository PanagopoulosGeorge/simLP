from rtec_lexer import RTECLexer
from rtec_parser import RTECParser
from distance_metric import event_description_distance
from partitioner import partition_event_description
from sys import argv
import logging

def parse_and_compute_distance(
							   generated_event_description=None,
							   ground_event_description=None,
	                           generated_rules_file = None, 
							   ground_rules_file = None, 
							   log_file='../logs/log.txt', 
							   generate_feedback=False,
							   ):
	
	def setup_logger(log_file, level=logging.INFO):
		"""To setup as many loggers as you want"""

		handler = logging.FileHandler(log_file, mode='w') 
		formatter = logging.Formatter('%(message)s')
		handler.setFormatter(formatter)

		logger = logging.getLogger(log_file)
		logger.setLevel(logging.INFO)
		logger.addHandler(handler)

		return logger
	logger = setup_logger(log_file)

	# init lexer and parsers for RTEC programs
	rtec_lexer = RTECLexer()
	lex = rtec_lexer.lexer

	rtec_parser1 = RTECParser()
	parser = rtec_parser1.parser
	if generated_event_description is None:
		with open(generated_rules_file) as f:
			parser.parse(f.read())
	else:
		parser.parse(generated_event_description)

	generated_event_description = rtec_parser1.event_description

	rtec_parser2 = RTECParser()
	parser = rtec_parser2.parser
	if ground_event_description is None:
		with open(ground_rules_file) as f:
			parser.parse(f.read())
	else:
		parser.parse(ground_event_description)

	ground_event_description = rtec_parser2.event_description

	# Event Description Preprocessing 
	## We split an input event description into multiple event descriptions, each defining the initiations, the terminations or the intervals of a different FVP.
	gen_ed_partitions = partition_event_description(generated_event_description)
	gen_ed_keys = gen_ed_partitions.keys()

	ground_ed_partitions = partition_event_description(ground_event_description)
	ground_ed_keys = ground_ed_partitions.keys()

	both_eds_keys = sorted(list(set(ground_ed_keys) & set(gen_ed_keys)))

	similarities = dict()
	all_feedback = dict() if generate_feedback else None
	
	for key in both_eds_keys:
		result = event_description_distance(gen_ed_partitions[key], ground_ed_partitions[key], logger, generate_feedback)
		if generate_feedback:
			optimal_matching, distances, similarity, feedback_data = result
			all_feedback[key] = feedback_data
		else:
			optimal_matching, distances, similarity = result[:3]
		similarities[key]=similarity

	logger.info("Computed similarity values: ")
	logger.info(similarities)
	logger.info("")

	logger.info("Concepts defined in both event descriptions: ")
	logger.info(both_eds_keys)
	logger.info("")
	print("Concepts defined in both event descriptions: ")
	print(both_eds_keys)
	print("")

	gen_ed_only_keys = list(set(gen_ed_keys) - set(ground_ed_keys))
	logger.info("Concepts defined only in generated event description: ")
	logger.info(gen_ed_only_keys)
	logger.info("")
	print("Concepts defined only in generated event description: ")
	print(gen_ed_only_keys)
	print("")

	ground_ed_only_keys = list(set(ground_ed_keys) - set(gen_ed_keys))
	logger.info("Concepts defined only in ground event description: ")
	logger.info(ground_ed_only_keys)
	logger.info("")
	print("Concepts defined only in ground event description: ")
	print(ground_ed_only_keys)
	print("")


	for key in ground_ed_only_keys:
		similarities[key]=0

	for key in similarities:
		print("Similarity for definition: " + str(key) + " is " + str(similarities[key]))
		logger.info("Similarity for definition: " + str(key) + " is " + str(similarities[key]))

	print("Event Description Similarity is: ")
	print(sum(similarities.values())/(len(both_eds_keys)+len(ground_ed_only_keys)))
	logger.info("Event Description Similarity is: ")
	logger.info(sum(similarities.values())/(len(both_eds_keys)+len(ground_ed_only_keys)))
	
	if generate_feedback:
		return optimal_matching, distances, similarity, all_feedback
	else:
		return optimal_matching, distances, similarity, 0


if __name__=="__main__":
	# Required 
	rules_file1 = """
	initiatedAt(highSpeedNearCoast(Vessel) = true, T) :-
    happensAt(velocity(Vessel, Speed), T),
    holdsAt(nearCoast(Vessel) = true, T),
    greater(Speed,5).

	"""
	rules_file2 = """
	initiatedAt(highSpeedNearCoast(Vessel)=true, T):-
    happensAt(velocity(Vessel, Speed, _, _), T),
    greater(Speed, 5),
    holdsAt(withinArea(Vessel, nearCoast)=true, T).


	"""
	# optional 
	log_file = "/Users/gphome/Desktop/projects/thesis-ds/simLP/unit_tests/test6/log.txt"
	generate_feedback = True
	print(generate_feedback)
	parse_and_compute_distance(generated_event_description=rules_file1, ground_event_description=rules_file2, log_file=log_file, generate_feedback=generate_feedback)
