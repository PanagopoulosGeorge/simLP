# Extension of a distance metric between ground logical atoms (see expression (9) in SPLICE paper)
# in order to measure the distance between logical programs.

from .event_description import Atom, Rule
import numpy as np
from scipy.optimize import linear_sum_assignment
from copy import deepcopy
import logging
from .atom_utils import atomIsVar, var_is_singleton, atomIsConst, atomIsComp, compute_var_routes, get_lists_size_and_pad

# Moved to atom_utils.py to avoid circular imports

def var_distance(var1, var2, var_routes1, var_routes2):
	if var_is_singleton(var1, var_routes1) and var_is_singleton(var2, var_routes2):
		return 0
	elif var_is_singleton(var1, var_routes1) or var_is_singleton(var2, var_routes2):
		return 1
	# Case: Both variables appear in the same atoms wrt nesting.
	elif sorted(var_routes1[var1])==sorted(var_routes2[var2]):
		return 0
	else:
		return 1

def const_distance(const1, const2):
	return 0 if const1 == const2 else 1

def comp_atom_distance(atom1, atom2, var_routes1, var_routes2, logger):
	''' We use the distance metric proposed by Nienhuys-Cheng (1997). '''
	if atom1.predicateName == atom2.predicateName and len(atom1.args) == len(atom2.args):
		distances_sum=0
		for i in range(len(atom1.args)):
			my_distance = atom_distance(atom1.args[i], atom2.args[i], var_routes1, var_routes2, logger) 
			distances_sum += my_distance
		return 1/(2*len(atom1.args)) * distances_sum
	else:
		return 1

def atom_distance(atom1, atom2, var_routes1, var_routes2, logger):
	if atomIsVar(atom1) and atomIsVar(atom2):
		return var_distance(atom1.predicateName, atom2.predicateName, var_routes1, var_routes2)
	elif atomIsConst(atom1) and atomIsConst(atom2): 
		return const_distance(atom1.predicateName, atom2.predicateName)
	elif atomIsComp(atom1) and atomIsComp(atom2):
		return comp_atom_distance(atom1, atom2, var_routes1, var_routes2, logger)
	else:
		return 1

def pad_lists(list1, list2, pad_item):
	def pad_list(mylist, n):
		for _ in range(n):
			mylist.append(pad_item)
	if len(list1)>len(list2):
		pad_list(list2, len(list1)-len(list2))
	elif len(list2)>len(list1):
		pad_list(list1, len(list2)-len(list1))

# Moved to atom_utils.py to avoid circular imports


def rule_distance(rule1, rule2, logger):

	var_routes1 = compute_var_routes(rule1)
	var_routes2 = compute_var_routes(rule2)

	head1 = rule1.head
	head2 = rule2.head
	
	head_distance = atom_distance(head1, head2, var_routes1, var_routes2, logger)
	#logger.info("Distance between rule heads: ")
	#logger.info(head_distance)

	body1 = deepcopy(rule1.body)
	body2 = deepcopy(rule2.body)

	m, k = get_lists_size_and_pad(body1, body2, Atom("&", []))
	
	c_array = np.array([[0.0 for _ in range(m)] for _ in range(m)])

	for i in range(m):
		for j in range(m):
			c_array[i][j] = atom_distance(body1[i], body2[j], var_routes1, var_routes2, logger)
	#logger.info("Body atom distances: ")
	#logger.info(c_array)

	row_ind, col_ind = linear_sum_assignment(c_array)
	#logger.info("Optimal Body Condition Assignment: ")
	#logger.info(col_ind)

	optimal_dist_sum = c_array[row_ind, col_ind].sum()
	#logger.info("Sum of distances for optimal body condition assignment: ")
	#logger.info(optimal_dist_sum)
	
	# We penalise the absence of a condition in the distance function. Therefore, we do not add (m-k) in the distance, like in the Michelioudakis paper.
	body_distance = optimal_dist_sum/m # 1/m*(m - k + optimal_dist_sum)
	#logger.info("Distance between rule bodies: ")
	#logger.info(body_distance)

	# We penalise head incongruity as much as the incongruity of a pair of body literals
	rule_distance = 1/(m+1)*(head_distance + m*body_distance)
	#logger.info("Distance between rules: ")
	#logger.info(rule_distance)

	rule_similarity = 1 - rule_distance
	#logger.info("Similarity of rules: ")
	#logger.info(rule_similarity)

	return rule_distance

def event_description_distance(event_description1, event_description2, logger, generate_feedback=False):
	"""
	Calculate the distance between two event descriptions (sets of Prolog rules).
	
	This function computes a normalized distance metric between two event descriptions
	by finding the optimal matching between their rules using the Hungarian algorithm
	(linear sum assignment). The distance is based on pairwise rule distances computed
	using structural and semantic similarity metrics.
	
	Args:
		event_description1 (EventDescription): The first event description (typically LLM-generated).
		event_description2 (EventDescription): The second event description (typically ground truth).
		logger (logging.Logger): Logger instance for recording detailed comparison information.
		generate_feedback (bool, optional): If True, generates detailed actionable feedback
			for improving the generated rules. Defaults to False.
	
	Returns:
		tuple: A 4-tuple containing:
			- col_ind (np.ndarray): Array of indices representing the optimal rule matching.
				col_ind[i] indicates which rule in event_description2 is matched to rule i 
				in event_description1.
			- distances (np.ndarray): Array of distances for each matched rule pair.
			- event_description_similarity (float): Overall similarity score between 0 and 1,
				where 1 indicates identical event descriptions and 0 indicates maximum distance.
			- feedback_data (dict or None): If generate_feedback=True, contains structured
				feedback including rule-by-rule analysis, summary statistics, and recommendations.
				None if generate_feedback=False.
	
	Algorithm:
		1. Pads the rule lists to equal length using dummy rules if necessary
		2. Computes pairwise rule distances forming a cost matrix
		3. Applies Hungarian algorithm to find optimal rule assignment
		4. Calculates normalized distance as: distance = (1/m) * sum(optimal_distances)
		5. Optionally generates detailed feedback for rule improvements
	
	Notes:
		- The function uses dummy rules (with head "_dummy_rule") for padding when the
		  event descriptions have different numbers of rules.
		- Distance is normalized by the number of rules (m) to ensure comparability.
		- Similarity is computed as: similarity = 1 - distance
		- When generate_feedback=True, detailed feedback is logged and returned for
		  LLM-based rule refinement.
	
	Example:
		>>> from distance_metric import event_description_distance
		>>> col_ind, distances, similarity, feedback = event_description_distance(
		...     generated_ed, ground_ed, logger, generate_feedback=True
		... )
		>>> print(f"Similarity: {similarity:.2%}")
	"""

	rules1 = event_description1.rules
	rules2 = event_description2.rules

	m, k = get_lists_size_and_pad(rules1, rules2, Rule(Atom("_dummy_rule", []), []))

	logger.info("Generated Definition: ")
	logger.info(event_description1)
	logger.info("")
	logger.info("Ground Definition: ")
	logger.info(event_description2)
	logger.info("")

	c_array = np.array([[0.0 for _ in range(m)] for _ in range(m)])

	for i in range(m):
		for j in range(m):
			#logger.info("\nComparing rules:\n " + str(rules1[i]) + " and\n" + str(rules2[j]))
			c_array[i][j] = rule_distance(rules1[i], rules2[j], logger)

	logger.info("Rule distances: ")
	logger.info(c_array)
	logger.info("\n")

	row_ind, col_ind = linear_sum_assignment(c_array)
	logger.info("Optimal Rule Assignment: ")
	logger.info(col_ind)
	logger.info("\n")

	for i in range(len(col_ind)):
		logger.info("We matched rule:")
		logger.info(event_description1.rules[i])
		logger.info("which has the distance array: " + str(c_array[i]) + "\n") 
		logger.info("with the following rule: ")
		logger.info(event_description2.rules[col_ind[i]])
		logger.info("Their distance is: " + str(c_array[i, col_ind[i]]) + "\n")
		logger.info("\n")

	optimal_dist_sum = c_array[row_ind, col_ind].sum()
	logger.info("Sum of distances for optimal rule assignment: ")
	logger.info(optimal_dist_sum)
	
	event_description_distance = 1/m*(optimal_dist_sum)
	logger.info("Distance between definitions: ")
	logger.info(event_description_distance)

	event_description_similarity = 1 - event_description_distance
	logger.info("Definition Similarity: ")
	logger.info(event_description_similarity)
	logger.info("")
	
	# Generate feedback if requested
	feedback_data = None
	if generate_feedback:
		# Import here to avoid circular dependency
		from feedback_generator import FeedbackGenerator
		feedback_gen = FeedbackGenerator(logger)
		feedback_data = feedback_gen.generate_event_description_feedback(event_description1, event_description2)
		formatted_feedback = feedback_gen.format_feedback_for_llm(feedback_data)
		logger.info("\n\n=== AUTOMATED FEEDBACK FOR LLM ===\n")
		logger.info(formatted_feedback)
		logger.info("\n=== END OF FEEDBACK ===\n")

	return col_ind, c_array[row_ind, col_ind], event_description_similarity, feedback_data


