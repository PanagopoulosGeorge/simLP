from .rtec_lexer import RTECLexer
from .rtec_parser import RTECParser
from .distance_metric import event_description_distance
from .partitioner import partition_event_description, find_fluent_type_mismatches
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

	# Check for fluent type mismatches (simple defined vs statically determined fluents)
	fluent_type_mismatches = find_fluent_type_mismatches(gen_ed_keys, ground_ed_keys)

	similarities = dict()
	all_feedback = ""
	
	# Initialize variables to avoid UnboundLocalError when no shared keys exist
	optimal_matching = None
	distances = None
	
	# Log and generate feedback for fluent type mismatches
	if fluent_type_mismatches:
		logger.info("=" * 60)
		logger.info("FLUENT DEFINITION TYPE MISMATCHES DETECTED:")
		logger.info("=" * 60)
		for mismatch in fluent_type_mismatches:
			fluent_name = mismatch['fluent_name']
			gen_type = mismatch['generated_type']
			ground_type = mismatch['ground_type']
			gen_predicates = [k[1] for k in mismatch['generated_keys']]
			ground_predicates = [k[1] for k in mismatch['ground_keys']]
			
			logger.info(f"  Fluent '{fluent_name}':")
			logger.info(f"    Generated uses: {gen_type} definition ({', '.join(gen_predicates)})")
			logger.info(f"    Ground uses: {ground_type} definition ({', '.join(ground_predicates)})")
			
			# Add to feedback
			if generate_feedback:
				if ground_type == 'static':
					all_feedback += (f"\n - FLUENT TYPE ERROR: Fluent '{fluent_name}' should be defined as a "
								   f"statically determined fluent using holdsFor/2, not as a simple fluent "
								   f"using {', '.join(gen_predicates)}. Statically determined fluents compute "
								   f"their intervals directly from conditions rather than through initiation/termination events.")
				else:
					all_feedback += (f"\n - FLUENT TYPE ERROR: Fluent '{fluent_name}' should be defined as a "
								   f"simple fluent using initiatedAt/2 and terminatedAt/2, not as a statically "
								   f"determined fluent using {', '.join(gen_predicates)}. Simple fluents are "
								   f"event-driven with explicit initiation and termination conditions.")
			
			# Assign 0 similarity for mismatched fluent types
			for key in mismatch['generated_keys']:
				similarities[key] = 0
		logger.info("")
	
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

	# Calculate denominator for average similarity
	# Include: shared concepts + ground-only concepts + mismatched fluent types (from ground side)
	num_ground_concepts = len(both_eds_keys) + len(ground_ed_only_keys)
	# Add ground keys from fluent type mismatches (these are concepts that exist but with wrong definition type)
	for mismatch in fluent_type_mismatches:
		for key in mismatch['ground_keys']:
			if key not in similarities:
				similarities[key] = 0
				num_ground_concepts += 1

	# print("Event Description Similarity is: ")
	average_similarity = sum(similarities.values()) / num_ground_concepts if num_ground_concepts > 0 else 0
	# print(average_similarity)
	logger.info("Event Description Similarity is: ")
	logger.info(average_similarity)
	
	if generate_feedback:
		return optimal_matching, distances, average_similarity, all_feedback
	else:
		return optimal_matching, distances, average_similarity, 0


if __name__=="__main__":
	# Required 
	rules_file2 = """
	initiatedAt(gap(Vessel)=nearPorts, T) :-
		happensAt(gap_start(Vessel), T),
		holdsAt(withinArea(Vessel, nearPorts)=true, T).

	terminatedAt(gap(Vessel)=_Status, T) :-
		happensAt(gap_end(Vessel), T).

	"""
	rules_file1 = """
	holdsFor(gap(Vessel)=nearPorts, T) :-
		happensAt(gap_start(Vessel), T),
		holdsAt(withinArea(Vessel, nearPorts)=true, T).
	"""
	# optional 
	log_file = "/Users/gphome/Desktop/projects/thesis-ds/simLP/unit_tests/test6/log.txt"
	generate_feedback = True
	print(generate_feedback)
	result = parse_and_compute_distance(generated_event_description=rules_file1, ground_event_description=rules_file2, log_file=log_file, generate_feedback=generate_feedback)
	print("similarity: ", result[2])
	print("feedback: ", result[3])