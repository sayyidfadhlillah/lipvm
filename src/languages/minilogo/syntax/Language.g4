grammar Language;

// Parser rules
start: (command (NEWLINE+ | EOF))* EOF;

move: 'move' x=expression y=expression;

color: 'color' code=COLOR;

draw: 'down' NEWLINE (move NEWLINE)* 'up';

block: LCBRACKET NEWLINE* (subcommands+=command NEWLINE*)* RCBRACKET;

expression: leftVal=term (PLUS rightVal=term)*;

term: leftVal=factor (STAR rightVal=factor)*;

varAssignment: identifier=ID '=' init=expression;

factor: NUMBER |
        LPAREN expression RPAREN |
        ID;

forloop
  : 'for' varAssignment 'to' end=expression block  # ForAssign
  | 'for' varCall=ID       'to' end=expression block  # ForVar
  ;

command: draw | move | color | forloop | varAssignment;

// Lexer rules
ID : [a-zA-Z][a-zA-Z0-9]*;
NUMBER: '-'?[0-9]+;

PLUS   : '+' ;
STAR   : '*' ;
LPAREN : '(' ;
RPAREN : ')' ;
LCBRACKET: '{';
RCBRACKET: '}';
HEX: '0'..'9' | 'a'..'f' | 'A'..'F';
COLOR: '#' (HEX HEX HEX | HEX HEX HEX HEX HEX HEX);

WS: [ ]+ -> skip;
NEWLINE: ('\r'? '\n' | '\r')+;