# Automated feedback generator for LLM-generated Prolog rules
# Provides detailed, actionable feedback based on distance metric analysis

from .event_description import Atom, Rule, EventDescription
from .atom_utils import (
    atomIsVar, atomIsConst, atomIsComp, 
    compute_var_routes, get_lists_size_and_pad
)
from scipy.optimize import linear_sum_assignment
import numpy as np
from copy import deepcopy
import logging

# Import atom_distance separately to avoid circular import
def get_atom_distance():
    from .distance_metric import atom_distance
    return atom_distance

class RuleFeedback:
    """Container for feedback about a single rule comparison"""
    def __init__(self, generated_rule, ground_rule, distance):
        self.generated_rule = generated_rule
        self.ground_rule = ground_rule
        self.distance = distance
        self.head_feedback = []
        self.body_feedback = []
        self.structure_feedback = []
        self.variable_feedback = []
        
    def add_head_feedback(self, feedback):
        self.head_feedback.append(feedback)
        
    def add_body_feedback(self, feedback):
        self.body_feedback.append(feedback)
        
    def add_structure_feedback(self, feedback):
        self.structure_feedback.append(feedback)
        
    def add_variable_feedback(self, feedback):
        self.variable_feedback.append(feedback)
        
    def to_dict(self):
        return {
            'generated_rule': str(self.generated_rule),
            'ground_rule': str(self.ground_rule),
            'distance': self.distance,
            'head_feedback': self.head_feedback,
            'body_feedback': self.body_feedback,
            'structure_feedback': self.structure_feedback,
            'variable_feedback': self.variable_feedback
        }

class FeedbackGenerator:
    """Generates detailed feedback for LLM rule generation"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
    
    def generate_fluent_type_feedback(self, mismatch):
        """Generate detailed feedback for fluent definition type mismatch.
        
        This method provides guidance when a fluent is incorrectly defined as a 
        simple fluent (using initiatedAt/terminatedAt) instead of a statically 
        determined fluent (using holdsFor), or vice versa.
        
        Args:
            mismatch: Dictionary containing:
                - fluent_name: Name of the mismatched fluent
                - generated_type: 'simple' or 'static'
                - ground_type: 'simple' or 'static'
                - generated_keys: List of partition keys used in generated description
                - ground_keys: List of partition keys used in ground truth
        
        Returns:
            str: Detailed feedback message explaining the error and how to fix it
        """
        fluent_name = mismatch['fluent_name']
        gen_type = mismatch['generated_type']
        ground_type = mismatch['ground_type']
        
        if ground_type == 'static':
            return (
                f"CRITICAL FLUENT TYPE ERROR: Fluent '{fluent_name}' is incorrectly defined.\n"
                f"  - Current (wrong): Simple fluent using initiatedAt/terminatedAt predicates\n"
                f"  - Expected (correct): Statically determined fluent using holdsFor/2 predicate\n\n"
                f"  Explanation: Statically determined fluents compute their intervals directly from "
                f"conditions that hold over time, rather than through discrete initiation and termination "
                f"events. The holdsFor/2 predicate defines when the fluent holds based on temporal "
                f"conditions.\n\n"
                f"  To fix: Replace your initiatedAt/terminatedAt rules with a holdsFor rule that "
                f"specifies when {fluent_name} holds based on the relevant conditions."
            )
        else:
            return (
                f"CRITICAL FLUENT TYPE ERROR: Fluent '{fluent_name}' is incorrectly defined.\n"
                f"  - Current (wrong): Statically determined fluent using holdsFor predicate\n"
                f"  - Expected (correct): Simple fluent using initiatedAt/2 and terminatedAt/2 predicates\n\n"
                f"  Explanation: Simple fluents are event-driven, meaning their state changes are "
                f"triggered by specific events. You need to define when the fluent starts (initiatedAt) "
                f"and when it ends (terminatedAt).\n\n"
                f"  To fix: Replace your holdsFor rule with separate initiatedAt and terminatedAt rules "
                f"that specify the events triggering the start and end of {fluent_name}."
            )
        
    def analyze_atom_difference(self, gen_atom, ground_atom, context=""):
        """Analyze differences between two atoms and generate specific feedback"""
        feedback = []
        
        if gen_atom.predicateName == "&":
            # Dummy atom used for padding
            return [f"Missing atom {str(ground_atom)} in " + context]
        if ground_atom.predicateName == "&":
            return [f"Atom: {str(gen_atom)} falsely defined in " + context]
            
        if gen_atom.predicateName != ground_atom.predicateName:
            # Different predicate names
            if atomIsComp(gen_atom) and atomIsComp(ground_atom):
                feedback.append(f"Wrong predicate: expected '{ground_atom.predicateName}' but got '{gen_atom.predicateName}'")
            else:
                feedback.append(f"Predicate mismatch: expected '{ground_atom.predicateName}' but got '{gen_atom.predicateName}'")
                
        elif len(ground_atom.args) != len(gen_atom.args):
            # Different number of arguments
            diff = len(ground_atom.args) - len(gen_atom.args)
            if diff > 0:
                feedback.append(f"Missing {diff} argument(s) in '{ground_atom.predicateName}' - expected {len(ground_atom.args)} arguments but got {len(gen_atom.args)}")
                # Check for underscore placeholders
                if any(arg.predicateName == "_" for arg in ground_atom.args if atomIsVar(arg)):
                    feedback.append(f"Consider adding underscore placeholders (_) for unused arguments in '{gen_atom.predicateName}'")
            else:
                feedback.append(f"Too many arguments in '{gen_atom.predicateName}' - expected {len(ground_atom.args)} but got {len(gen_atom.args)}")
                
        elif atomIsComp(gen_atom) and atomIsComp(ground_atom):
            # Same predicate, same arity, but different internal structure
            for i, (arg1, arg2) in enumerate(zip(gen_atom.args, ground_atom.args)):
                arg_feedback = self.analyze_atom_difference(arg1, arg2, f"{gen_atom.predicateName} argument {i+1}")
                feedback.extend(arg_feedback)
                
        return feedback
    
    def analyze_body_matching(self, body1, body2, var_routes1, var_routes2):
        """Analyze body atom matching and generate feedback"""
        feedback = []
        
        # Copy bodies to avoid modifying originals
        body1_copy = deepcopy(body1)
        body2_copy = deepcopy(body2)
        
        # Pad lists to same length
        m, k = get_lists_size_and_pad(body1_copy, body2_copy, Atom("&", []))
        
        # Compute cost matrix
        c_array = np.array([[0.0 for _ in range(m)] for _ in range(m)])
        for i in range(m):
            for j in range(m):
                atom_distance = get_atom_distance()
                c_array[i][j] = atom_distance(body1_copy[i], body2_copy[j], var_routes1, var_routes2, self.logger)
                
        # Find optimal matching
        row_ind, col_ind = linear_sum_assignment(c_array)
        
        # Generate feedback based on matching
        matched_atoms = []
        for i in range(len(col_ind)):
            gen_atom = body1_copy[i]
            ground_atom = body2_copy[col_ind[i]]
            distance = c_array[i, col_ind[i]]
            
            if distance > 0:
                atom_feedback = self.analyze_atom_difference(gen_atom, ground_atom, "body")
                if atom_feedback:
                    matched_atoms.append({
                        'generated': str(gen_atom),
                        'expected': str(ground_atom),
                        'feedback': atom_feedback,
                        'distance': distance
                    })
                    
        # Check for ordering issues
        if len(body1) == len(body2) and all(col_ind[i] != i for i in range(len(col_ind))):
            feedback.append("Consider reordering body atoms to match ground truth pattern")
            
        return feedback, matched_atoms
    
    def analyze_variable_usage(self, rule1, rule2):
        """Analyze variable usage patterns and provide feedback"""
        feedback = []
        
        var_routes1 = compute_var_routes(rule1)
        var_routes2 = compute_var_routes(rule2)
        
        # Check for singleton variables
        singleton_vars1 = {var for var in var_routes1 if len(var_routes1[var]) == 1}
        singleton_vars2 = {var for var in var_routes2 if len(var_routes2[var]) == 1}
        
        # Check for missing underscores
        if len(singleton_vars2) > len(singleton_vars1):
            non_underscore_singletons = [var for var in singleton_vars1 if not var.startswith("_")]
            if non_underscore_singletons:
                feedback.append(f"Consider using underscore (_) for singleton variables: {', '.join(non_underscore_singletons)}")
                
        return feedback, var_routes1, var_routes2
    
    def generate_rule_feedback(self, rule1, rule2):
        """Generate comprehensive feedback for a rule pair"""
        feedback = RuleFeedback(rule1, rule2, 0)
        
        # Analyze variable usage
        var_feedback, var_routes1, var_routes2 = self.analyze_variable_usage(rule1, rule2)
        feedback.variable_feedback.extend(var_feedback)
                
        # Analyze body
        body_feedback, matched_atoms = self.analyze_body_matching(
            rule1.body, rule2.body, var_routes1, var_routes2
        )
        feedback.body_feedback.extend(body_feedback)
        
        # Add detailed atom-level feedback
        for match in matched_atoms:
            for fb in match['feedback']:
                feedback.body_feedback.append(f"In atom '{match['generated']}': {fb}")
                
        # Structure feedback
        if len(rule1.body) != len(rule2.body):
            diff = len(rule2.body) - len(rule1.body)
            if diff > 0:
                feedback.structure_feedback.append(f"Missing {diff} condition(s) in rule body")
            else:
                feedback.structure_feedback.append(f"Extra {-diff} condition(s) in rule body")
                
        return feedback
    
    def generate_event_description_feedback(self, generated_ed, ground_ed):
        """Generate feedback for entire event description"""
        all_feedback = {
            'rules': [],
            'summary': {},
            'overall_recommendations': []
        }
        
        # Match rules
        rules1 = generated_ed.rules
        rules2 = ground_ed.rules
        
        m, k = get_lists_size_and_pad(rules1, rules2, Rule(Atom("_dummy_rule", []), []))
        
        # Compute distances for optimal matching
        from .distance_metric import rule_distance
        c_array = np.array([[0.0 for _ in range(m)] for _ in range(m)])
        for i in range(m):
            for j in range(m):
                c_array[i][j] = rule_distance(rules1[i], rules2[j], self.logger)
                
        row_ind, col_ind = linear_sum_assignment(c_array)
        
        # Generate feedback for each matched rule
        for i in range(len(col_ind)):
            gen_rule = rules1[i]
            ground_rule = rules2[col_ind[i]]
            distance = c_array[i, col_ind[i]]
            if gen_rule.head.predicateName == "_dummy_rule":
                # LLM should have generated a rule but it didn't
                all_feedback['overall_recommendations'].append(f" - An extra rule is in the ground truth but not in the generated event description")
                continue
            if ground_rule.head.predicateName == "_dummy_rule":
                # LLM should have generated a rule but it didn't
                all_feedback['overall_recommendations'].append(f" - Generated rule {str(gen_rule)} is not in the ground truth. It should not be defined.")
                continue
            rule_feedback = self.generate_rule_feedback(gen_rule, ground_rule)
            rule_feedback.distance = distance
            all_feedback['rules'].append(rule_feedback.to_dict())
                
        # Generate summary statistics
        all_feedback['summary'] = {
            'total_rules_generated': len([r for r in rules1 if r.head.predicateName != "_dummy_rule"]),
            'total_rules_expected': len([r for r in rules2 if r.head.predicateName != "_dummy_rule"]),
            'average_distance': np.mean([r['distance'] for r in all_feedback['rules']]) if all_feedback['rules'] else 0
        }
        
        # Overall recommendations
        if all_feedback['summary']['total_rules_generated'] > all_feedback['summary']['total_rules_expected']:
            all_feedback['overall_recommendations'].append(
                f"Generated {all_feedback['summary']['total_rules_generated']} rules but only {all_feedback['summary']['total_rules_expected']} expected - review if all rules are necessary"
            )
        elif all_feedback['summary']['total_rules_generated'] < all_feedback['summary']['total_rules_expected']:
            all_feedback['overall_recommendations'].append(
                f"Missing {all_feedback['summary']['total_rules_expected'] - all_feedback['summary']['total_rules_generated']} rule(s) - check if all cases are covered"
            )
            
        return all_feedback
    
    def format_feedback_for_llm(self, feedback_data):
        """Format feedback in a clear, actionable way for LLM consumption"""
        output = []
        output.append("## Event Description Analysis and Feedback\n")
        
        # Summary
        summary = feedback_data['summary']
        output.append(f"### Summary")
        output.append(f"- Generated {summary['total_rules_generated']} rules (expected {summary['total_rules_expected']})")
        output.append(f"- Average similarity: {1 - summary['average_distance']:.2%}\n")
        
        # Rule-by-rule feedback
        output.append("### Detailed Rule Feedback\n")
        
        for i, rule_fb in enumerate(feedback_data['rules'], 1):
            output.append(f"#### Rule {i} (Similarity: {1 - rule_fb['distance']:.2%})")
            output.append(f"**Generated:**")
            output.append(f"```prolog\n{rule_fb['generated_rule'].strip()}\n```")
            output.append(f"**Expected:**")
            output.append(f"```prolog\n{rule_fb['ground_rule'].strip()}\n```")
            
            # Collect all feedback
            all_issues = []
            
            if rule_fb['head_feedback']:
                all_issues.extend([f"HEAD: {fb}" for fb in rule_fb['head_feedback']])
                
            if rule_fb['body_feedback']:
                all_issues.extend([f"BODY: {fb}" for fb in rule_fb['body_feedback']])
                
            if rule_fb['structure_feedback']:
                all_issues.extend([f"STRUCTURE: {fb}" for fb in rule_fb['structure_feedback']])
                
            if rule_fb['variable_feedback']:
                all_issues.extend([f"VARIABLES: {fb}" for fb in rule_fb['variable_feedback']])
                
            if all_issues:
                output.append("\n**Issues to fix:**")
                for issue in all_issues:
                    output.append(f"- {issue}")
            else:
                output.append("\n**This rule matches perfectly!**")
                
            output.append("")  # Empty line between rules
            
        # Overall recommendations
        if feedback_data['overall_recommendations']:
            output.append("### Overall Recommendations")
            for rec in feedback_data['overall_recommendations']:
                output.append(f"- {rec}")
                
        return "\n".join(output)
