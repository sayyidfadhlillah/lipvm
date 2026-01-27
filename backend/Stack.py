class Stack:
    
  def __init__(self): 
    self._elements = [] 

  def __len__(self): 
    return len(self._elements) 

  def push(self,item): 
    self._elements.insert(0,item) 

  def peek(self): 
    if len(self) == 0: 
      raise Exception("peek() called on empty stack.") 
    return self._elements[0] 

  def pop(self): 
    if len(self) == 0: 
      raise Exception("pop() called on empty stack.") 
    return self._elements.pop(0) 

  def __repr__(self):
    return str(self)

  def __str__(self): 
    return  '[' + ', '.join([str(element) for element in self._elements]) + ']'