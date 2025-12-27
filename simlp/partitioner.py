from .event_description import EventDescription


def get_defined_concept_key(atom):
	if atom.predicateName=="initiatedAt":
		return (atom.args[0].args[0].predicateName, "initiatedAt")
	elif atom.predicateName=="terminatedAt":
		return (atom.args[0].args[0].predicateName, "terminatedAt")
	elif atom.predicateName=="holdsFor":
		return (atom.args[0].args[0].predicateName, "holdsFor")
	else:
		return "other"


def get_fluent_name(key):
	"""Extract just the fluent name from a partition key.
	
	Args:
		key: A partition key, either a tuple (fluent_name, predicate_type) or "other"
	
	Returns:
		str or None: The fluent name if key is a valid tuple, None otherwise
	"""
	if isinstance(key, tuple) and len(key) == 2:
		return key[0]
	return None


def get_fluent_definition_type(key):
	"""Get the definition type (simple vs static) from a partition key.
	
	Simple defined fluents use initiatedAt/terminatedAt predicates.
	Statically determined fluents use holdsFor predicate.
	
	Args:
		key: A partition key tuple (fluent_name, predicate_type)
	
	Returns:
		str or None: 'simple' for initiatedAt/terminatedAt, 'static' for holdsFor, None otherwise
	"""
	if isinstance(key, tuple) and len(key) == 2:
		predicate = key[1]
		if predicate in ('initiatedAt', 'terminatedAt'):
			return 'simple'  # Simple defined fluent
		elif predicate == 'holdsFor':
			return 'static'  # Statically determined fluent
	return None


def find_fluent_type_mismatches(gen_keys, ground_keys):
	"""Find fluents that are defined with different types in generated vs ground truth.
	
	Detects when a fluent is defined as a simple fluent (initiatedAt/terminatedAt) in one
	event description but as a statically determined fluent (holdsFor) in another.
	
	Args:
		gen_keys: Keys from the generated event description partitions
		ground_keys: Keys from the ground truth event description partitions
	
	Returns:
		list: List of mismatch dictionaries, each containing:
			- fluent_name: Name of the mismatched fluent
			- generated_keys: List of keys used in generated description for this fluent
			- ground_keys: List of keys used in ground truth for this fluent
			- generated_type: 'simple' or 'static'
			- ground_type: 'simple' or 'static'
	"""
	# Group keys by fluent name
	gen_fluents = {}
	for k in gen_keys:
		fluent_name = get_fluent_name(k)
		if fluent_name:
			if fluent_name not in gen_fluents:
				gen_fluents[fluent_name] = []
			gen_fluents[fluent_name].append(k)
	
	ground_fluents = {}
	for k in ground_keys:
		fluent_name = get_fluent_name(k)
		if fluent_name:
			if fluent_name not in ground_fluents:
				ground_fluents[fluent_name] = []
			ground_fluents[fluent_name].append(k)
	
	mismatches = []
	# Check fluents that appear in both but with different definition types
	for fluent_name in set(gen_fluents.keys()) & set(ground_fluents.keys()):
		gen_types = set(get_fluent_definition_type(k) for k in gen_fluents[fluent_name])
		ground_types = set(get_fluent_definition_type(k) for k in ground_fluents[fluent_name])
		
		# Remove None values
		gen_types.discard(None)
		ground_types.discard(None)
		
		# Check if types are different (e.g., generated uses simple, ground uses static)
		if gen_types and ground_types and gen_types != ground_types:
			mismatches.append({
				'fluent_name': fluent_name,
				'generated_keys': gen_fluents[fluent_name],
				'ground_keys': ground_fluents[fluent_name],
				'generated_type': list(gen_types)[0] if len(gen_types) == 1 else 'mixed',
				'ground_type': list(ground_types)[0] if len(ground_types) == 1 else 'mixed'
			})
	
	return mismatches


def partition_event_description(event_description):
	partitioned_event_description = dict()
	for rule in event_description.rules:
		defined_concept_key = get_defined_concept_key(rule.head)
		if defined_concept_key not in partitioned_event_description:
			partitioned_event_description[defined_concept_key] = EventDescription()
		partitioned_event_description[defined_concept_key].add_rule(rule.head, rule.body)
	return partitioned_event_description


