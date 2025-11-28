from .rtec_lexer import RTECLexer
from .rtec_parser import RTECParser
from .distance_metric import event_description_distance
from .partitioner import partition_event_description
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
	"""
	Parse Prolog event descriptions and compute similarity metrics between them.
	
	Compare LLM-generated Prolog rules against ground truth definitions and 
	provide automated feedback for rule refinement. 
	
	flag to enable detailed feedback generation:
	generate_feedback = True.
	
	Args:
		generated_event_description (str, optional): Raw Prolog code string for the
			generated event description. If provided, this takes precedence over
			generated_rules_file. Defaults to None.
		ground_event_description (str, optional): Raw Prolog code string for the
			ground truth event description. If provided, this takes precedence over
			ground_rules_file. Defaults to None.
		generated_rules_file (str, optional): Path to file containing generated
			Prolog rules. Used only if generated_event_description is None.
			Defaults to None.
		ground_rules_file (str, optional): Path to file containing ground truth
			Prolog rules. Used only if ground_event_description is None.
			Defaults to None.
		log_file (str, optional): Path to output log file where detailed comparison
			results will be written. Defaults to '../logs/log.txt'.
		generate_feedback (bool, optional): If True, generates detailed actionable
			feedback for improving the generated rules. Defaults to False.
	
	Returns:
		tuple: A 4-tuple containing:
			- optimal_matching (np.ndarray): Optimal rule assignment indices from the
			  last concept processed.
			- distances (np.ndarray): Distance values for each matched rule pair from
			  the last concept processed.
			- similarity (float): Overall similarity score (0-1) for the last concept
			  processed.
			- all_feedback str: If generate_feedback=True, returns a dictionary
			  mapping concept keys to their feedback data. If False, returns 0.
	
	Workflow:
		1. Sets up logging to the specified log file
		2. Parses both event descriptions using RTEC parser
		3. Partitions event descriptions by concept (FVP definitions)
		4. Computes similarity for each shared concept using event_description_distance
		5. Identifies concepts unique to each event description
		6. Calculates overall event description similarity across all concepts
		7. Optionally generates and logs detailed feedback for rule improvement
	
	Example:
		>>> # Using string input
		>>> rules_gen = "initiatedAt(event(X)=true, T) :- condition(X, T)."
		>>> rules_ground = "initiatedAt(event(X)=true, T) :- condition(X, T)."
		>>> result = parse_and_compute_distance(
		...     generated_event_description=rules_gen,
		...     ground_event_description=rules_ground,
		...     log_file='logs/comparison.txt',
		...     generate_feedback=True
		... )
		
		>>> # Using file input
		>>> result = parse_and_compute_distance(
		...     generated_rules_file='rules/generated.prolog',
		...     ground_rules_file='rules/ground_truth.prolog',
		...     generate_feedback=True
		... )
	"""
	
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
	try:
		if generated_event_description is None:
			with open(generated_rules_file) as f:
				parser.parse(f.read())
		else:
			parser.parse(generated_event_description)
	except Exception as e:
		logger.error(f"Error parsing generated event description: {e}")
		return None, None, None, None

	generated_event_description = rtec_parser1.event_description

	rtec_parser2 = RTECParser()
	parser = rtec_parser2.parser
	try:
		if ground_event_description is None:
			with open(ground_rules_file) as f:
				parser.parse(f.read())
		else:
			parser.parse(ground_event_description)
	except Exception as e:
		logger.error(f"Error parsing ground event description: {e}")
		return None, None, None, None

	ground_event_description = rtec_parser2.event_description

	# Event Description Preprocessing 
	## We split an input event description into multiple event descriptions, each defining the initiations, the terminations or the intervals of a different FVP.
	gen_ed_partitions = partition_event_description(generated_event_description)
	gen_ed_keys = gen_ed_partitions.keys()

	ground_ed_partitions = partition_event_description(ground_event_description)
	ground_ed_keys = ground_ed_partitions.keys()

	both_eds_keys = sorted(list(set(ground_ed_keys) & set(gen_ed_keys)))

	similarities = dict()
	all_feedback = ""
	
	for key in both_eds_keys:
		result = event_description_distance(gen_ed_partitions[key], ground_ed_partitions[key], logger, generate_feedback)
		if generate_feedback:
			optimal_matching, distances, similarity, feedback_data = result
			all_feedback += "\n".join(feedback_data['overall_recommendations'])
		else:
			optimal_matching, distances, similarity = result[:3]
		similarities[key]=similarity

	logger.info("Computed similarity values: ")
	logger.info(similarities)
	logger.info("")

	logger.info("Concepts defined in both event descriptions: ")
	logger.info(both_eds_keys)
	logger.info("")
	# print("Concepts defined in both event descriptions: ")
	# print(both_eds_keys)
	# print("")

	gen_ed_only_keys = list(set(gen_ed_keys) - set(ground_ed_keys))
	logger.info("Concepts defined only in generated event description: ")
	logger.info(gen_ed_only_keys)
	logger.info("")
	# print("Concepts defined only in generated event description: ")
	# print(gen_ed_only_keys)
	# print("")

	ground_ed_only_keys = list(set(ground_ed_keys) - set(gen_ed_keys))
	logger.info("Concepts defined only in ground event description: ")
	logger.info(ground_ed_only_keys)
	logger.info("")
	# print("Concepts defined only in ground event description: ")
	# print(ground_ed_only_keys)
	# print("")


	for key in ground_ed_only_keys:
		similarities[key]=0

	for key in similarities:
		# print("Similarity for definition: " + str(key) + " is " + str(similarities[key]))
		logger.info("Similarity for definition: " + str(key) + " is " + str(similarities[key]))

	# print("Event Description Similarity is: ")
	average_similarity = sum(similarities.values())/(len(both_eds_keys)+len(ground_ed_only_keys))
	# print(average_similarity)
	logger.info("Event Description Similarity is: ")
	logger.info(sum(similarities.values())/(len(both_eds_keys)+len(ground_ed_only_keys)))
	
	if generate_feedback:
		return optimal_matching, distances, average_similarity, all_feedback
	else:
		return optimal_matching, distances, average_similarity, 0


if __name__=="__main__":
	# Required 
	rules_file1 = """
	initiatedAt(gap(Vessel)=nearPorts, T) :-
		happensAt(gap_start(Vessel), T),
		holdsAt(withinArea(Vessel, nearPorts)=true, T).

	terminatedAt(gap(Vessel)=_Status, T) :-
		happensAt(gap_end(Vessel), T).

	"""
	rules_file2 = """
	initiatedAt(gap(Vessel)=nearPorts, T) :-
		happensAt(gap_start(Vessel), T),
		holdsAt(withinArea(Vessel, nearPorts)=true, T).

	initiatedAt(gap(Vessel)=farFromPorts, T) :-
		happensAt(gap_start(Vessel), T),
		not holdsAt(withinArea(Vessel, nearPorts)=true, T).

	terminatedAt(gap(Vessel)=_Status, T) :-
		happensAt(gap_end(Vessel), T).
	"""
	# optional 
	log_file = "/Users/gphome/Desktop/projects/thesis-ds/simLP/unit_tests/test6/log.txt"
	generate_feedback = True
	print(generate_feedback)
	result = parse_and_compute_distance(generated_event_description=rules_file1, ground_event_description=rules_file2, log_file=log_file, generate_feedback=generate_feedback)
	print("similarity: ", result[2])
	print("feedback: ", result[3])