"""
Provides a test case for issue 283 - "Inheritance breaks".

The issue is outlined here: https://github.com/neo4j-contrib/neomodel/issues/283
More infomration about the same issue at: https://github.com/aanastasiou/neomodelInheritanceTest

The following example uses a recursive relationship for economy, but the 
idea remains the same: "Instantiate the correct type of node at the end of 
a relationship as specified by the model"
"""

import os
import neomodel
import datetime
import pytest

def _setup():
    # Setting up
    neo4jUsername = os.environ['NEO4J_USERNAME']
    neo4jPassword = os.environ['NEO4J_PASSWORD']
    dbConURI = "bolt://{uname}:{pword}@localhost:7687".format(uname=neo4jUsername, pword=neo4jPassword)

    #This must be called before any further calls to neomodel.
    neomodel.db.set_connection(dbConURI)    
    
def _cleanup():
    neomodel.db.cypher_query("match (a:BasePerson) detach delete a")
    neomodel.db.cypher_query("match (a:BaseOtherPerson) detach delete a")
    


class PersonalRelationship(neomodel.StructuredRel):
    """
    A very simple relationship between two basePersons that simply records 
    the date at which an acquaintance was established.
    This relationship should be carried over to anything that inherits from 
    basePerson without any further effort.
    """
    on_date = neomodel.DateProperty(default_now = True)
    
class BasePerson(neomodel.StructuredNode):
    """
    Base class for defining some basic sort of an actor.
    """
    name = neomodel.StringProperty(required = True, unique_index = True)
    friends_with = neomodel.RelationshipTo("BasePerson", "FRIENDS_WITH", model = PersonalRelationship)
    
class TechnicalPerson(BasePerson):
    """
    A Technical person specialises BasePerson by adding their expertise
    """
    expertise = neomodel.StringProperty(required = True)
    
class PilotPerson(BasePerson):
    """
    A pilot person specialises BasePerson by adding the type of airplane they can operate
    """
    airplane = neomodel.StringProperty(required = True)
    
class BaseOtherPerson(neomodel.StructuredNode):
    """
    An obviously "wrong" class of actor to befriend BasePersons with
    """
    car_color = neomodel.StringProperty(required = True)
    
class SomePerson(BaseOtherPerson):
    """
    Concrete class that simply derives from BaseOtherPerson
    """
    pass  


def test_issue_283_1():
    """
    Node objects at the end of relationships are instantiated to their 
    corresponding object
    """
        
    _setup()
    # Create a few entities
    A = TechnicalPerson.get_or_create({"name":"Grumpy", "expertise":"Grumpiness"})[0]
    B = TechnicalPerson.get_or_create({"name":"Happy", "expertise":"Unicorns"})[0]
    C = TechnicalPerson.get_or_create({"name":"Sleepy", "expertise":"Pillows"})[0]
    
    # Add connections
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)
    
    # If A is friends with B, then A's friends_with objects should be TechnicalPerson (!NOT basePerson!)
    assert type(A.friends_with[0]) is TechnicalPerson    
    _cleanup()
        
def test_issue_283_2():    
    """
    Objects descending from the specified class of a relationship's end-node are also 
    perfectly valid to appear as end-node values too
    """
    
    _setup()
    #Create a few entities
    # Technical Persons
    A = TechnicalPerson.get_or_create({"name":"Grumpy", "expertise":"Grumpiness"})[0]
    B = TechnicalPerson.get_or_create({"name":"Happy", "expertise":"Unicorns"})[0]
    C = TechnicalPerson.get_or_create({"name":"Sleepy", "expertise":"Pillows"})[0]
    
    # Pilot Persons
    D = PilotPerson.get_or_create({"name":"Porco Rosso", "airplane":"Savoia-Marchetti"})[0]
    E = PilotPerson.get_or_create({"name":"Jack Dalton", "airplane":"Beechcraft Model 18"})[0]
    
    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine
    
    # TechnicalPersons befriend Technical Persons
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)
    
    # Pilot Persons befriend Technical Persons
    D.friends_with.connect(E)
    
    # Technical Persons befriend Pilot Persons
    A.friends_with.connect(D)
    E.friends_with.connect(C)
    
    # This now means that friends_with of a TechnicalPerson can 
    # either be TechnicalPerson or Pilot Person (!NOT basePerson!)
    
    assert (type(A.friends_with[0]) is TechnicalPerson) or (type(A.friends_with[0]) is PilotPerson)
    assert (type(A.friends_with[1]) is TechnicalPerson) or (type(A.friends_with[1]) is PilotPerson)
    assert type(D.friends_with[0]) is PilotPerson
    _cleanup()
    
        
def test_issue_283_3():        
    """
    If a connection between wrong types is attempted, raise an exception
    """
    
    _setup()
    #Create a few entities
    # Technical Persons
    A = TechnicalPerson.get_or_create({"name":"Grumpy", "expertise":"Grumpiness"})[0]
    B = TechnicalPerson.get_or_create({"name":"Happy", "expertise":"Unicorns"})[0]
    C = TechnicalPerson.get_or_create({"name":"Sleepy", "expertise":"Pillows"})[0]
    
    # Pilot Persons
    D = PilotPerson.get_or_create({"name":"Porco Rosso", "airplane":"Savoia-Marchetti"})[0]
    E = PilotPerson.get_or_create({"name":"Jack Dalton", "airplane":"Beechcraft Model 18"})[0]
    
    #Some Person    
    F = SomePerson(car_color = "Blue").save()
    
    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)
    D.friends_with.connect(E)
    A.friends_with.connect(D)
    E.friends_with.connect(C)
    
    # Trying to befriend a Technical Person with Some Person should raise an exception
    with pytest.raises(ValueError):
        A.friends_with.connect(F)   
    
    _cleanup()
