# Utility functions for atom analysis
# Extracted from distance_metric.py to avoid circular imports

from event_description import Atom

def atomIsVar(atom):
    return atom.predicateName[0].isupper() or atom.predicateName[0]=="_"

def var_is_singleton(var, var_routes):
    return var[0]=="_" or len(var_routes[var])==1

def atomIsConst(atom):
    return (atom.predicateName[0].islower() or atom.predicateName[0]=="&" or atom.predicateName.isnumeric()) and len(atom.args)==0 

def atomIsComp(atom):
    return len(atom.args)>0

def compute_var_routes(rule):
    var_routes = dict()
    
    def find_var_routes_in_atom(atom, route):
        # For free variables, we do nothing.
        if atom.predicateName[0].isupper(): 
            if atom.predicateName in var_routes:
                var_routes[atom.predicateName].append(route)
            else:
                var_routes[atom.predicateName] = [route]
        else:
            for arg_index in range(0, len(atom.args)):
                find_var_routes_in_atom(atom.args[arg_index], route + [(atom.predicateName, arg_index)])

    find_var_routes_in_atom(rule.head, list())
    for atom in rule.body:
        find_var_routes_in_atom(atom, list())
    return var_routes

def get_lists_size_and_pad(list1, list2, pad_item):
    def pad_list(mylist, n):
        for _ in range(n):
            mylist.append(pad_item)

    if len(list1)==len(list2):
        m = len(list1)
        k = len(list1)
    elif len(list1)>len(list2):
        m = len(list1)
        k = len(list2)
        pad_list(list2, m-k)
    elif len(list2)>len(list1):
        m = len(list2)
        k = len(list1)
        pad_list(list1, m-k)

    return m, k
