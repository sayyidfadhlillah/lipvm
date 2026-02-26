grammar Language;

// == Define parser rules ==

machine: 'statemachine' name=ID;

events: 'events' (name=ID)*;

initial: 'initialState' name=ID;

state: 'state' name=ID transitions=transition* activate_func=activate? tick_func=tick? 'end';

transition: name=ID '=>' stateName=ID;

activate: 'activate:' body;
tick: 'tick:' body;

conditional: 'if' LPAREN condition=expression RPAREN then_body=body
('else' else_body=body)?;

// Expressions
variable: variableName=ID;
literal: variable | NUMBER | STRING | TRUE | FALSE;
driver_call: 'mch_driver.' driverCall=call;

expression:
    leftOperand=expression op=OPERATOR rightOperand=expression
    | literal
    | LPAREN expression RPAREN
    | driver_call;

// Function definition and call
arguments: expression (',' expression)*;
call: functionName=ID LPAREN args=arguments? RPAREN;

halt: 'halt' LPAREN RPAREN;
body: LCBRACKET (assignment | call | halt | forloop | conditional | driver_call)* RCBRACKET;

// Variable definition
assignment: variableName=ID '=' value=expression;

// Control structures
forloop
  : 'for' assignment 'to' end=expression body
  | 'for' variable 'to' end=expression body
  ;

// Main rule
main: machine events initial state*;

// == Define lexer rules ==
ID : [a-zA-Z][a-zA-Z0-9_]*;
NUMBER: '-'?[0-9]+;
STRING : '"' .*? '"' ;

OPERATOR: '+' | '-' | '*' | '/' | '&&' | '||';

LPAREN : '(' ;
RPAREN : ')' ;
LCBRACKET: '{';
RCBRACKET: '}';
TRUE: 'True';
FALSE: 'False';
MCH_DRIVER: 'mch_driver';

WS: [ \t\r\n]+ -> skip;
