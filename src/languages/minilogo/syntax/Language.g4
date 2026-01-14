grammar Language;

// Parser rules
move: 'move' x=NUMBER y=NUMBER;

color: 'color' code=COLOR;

draw: 'down' NEWLINE (move NEWLINE)* 'up';

start: ((draw | move | color) NEWLINE)*;

// Lexer rules
NUMBER: '-'?[0-9]+;

HEX: '0'..'9' | 'a'..'f' | 'A'..'F';
COLOR: '#' (HEX HEX HEX | HEX HEX HEX HEX HEX HEX);

WS: [ ]+ -> skip;
NEWLINE: ('\r'? '\n' | '\r')+;