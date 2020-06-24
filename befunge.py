#!/usr/bin/env python

import logging
import random

#########
# Lexing
#########
class Token:
    """A Befunge token"""
    value = None
    string_format = "{type}('{value}')"

    def __init__(self,value=None):
        self.value = value

    def __str__(self):
        return(self.string_format.format(type=self.__class__.__name__,value=self.value))

    def __repr__(self):
        return self.__str__()


class EofToken(Token):
    """End-of-file token"""
    pass


class DigitToken(Token):
    """Digit [0-9] token"""
    string_format = "{type}({value})"


class StringToken(Token):
    """String token"""
    pass


class CommandToken(Token):
    """A command token"""
    pass


class Lexer:
    """A lexical analyzer for a Befunge program"""

    program = None
    command_lexemes = None
    xpos = 0
    ypos = 0
    dx = 1
    dy = 0

    def __init__(self):
        self.command_lexemes = Command.dict().keys()
        self.program = []

    def read(self,string):
        """Read program *string*"""
        for line in string.split('\n'):
            self.program.append(list(line))
        logging.debug("read finished.  program={}".format(self.program))

    def advance(self):
        """Advance the pointer."""
        self.xpos += self.dx
        self.ypos += self.dy


    @property
    def current_character(self):
        """The character at the program's current position."""
        try:
            char = self.program[self.ypos][self.xpos]
        except IndexError:
            raise
        return char

    def string(self):
        """Read tokens in string mode.
        
        Scans characters until the next :code:`"` is found, 
        yielding :class:`StringToken`s.
        """
        try:
            while self.current_character != '"':
                yield StringToken(self.current_character)
                self.advance()
        except IndexError:
            raise SyntaxError("Program ended in string mode")


    def tokens(self):
        """Iterate over the program's tokens"""
        while True:
            logging.debug("position: ({},{})".format(self.xpos,self.ypos))
            try:
                char = self.program[self.ypos][self.xpos]
            except IndexError:
                yield EofToken()
                break
            if char.isdigit():
                yield DigitToken(int(char))
            elif char == '"':
                self.advance()
                yield from self.string()
            elif char in self.command_lexemes:
                yield CommandToken(char)
            else:
                raise SyntaxError("Illegal character: {}".format(char))
            self.advance()

###########
# Commands
###########
class Command:
    """A Befunge command"""

    token = None
    """The character triggering this command"""

    interpreter = None
    """The interpreter object the command acts on"""

    def __init__(self,interpreter):
        self.interpreter = interpreter

    def execute(self):
        raise NotImplementedError("{}.execute".format(self.__class__.__name__))

    @classmethod
    def get_subclasses(cls):
        """All descendant classes of this class.
        
        Acknowledgements to Kimvais via `Stackoverflow`:_
        
        __ https://stackoverflow.com/a/33607093/297797
        """
        for subclass in cls.__subclasses__():
            yield from subclass.get_subclasses()
            yield subclass    

    @classmethod
    def dict(cls):
        """A dictionary (*token*,*class*) mapping token (characters) to command (classes)"""

        commands = {
            cls.token : cls
            for cls in cls.get_subclasses()
            if cls.token is not None
        }
        return commands


class NoopCommand(Command):
    """No-op. Does nothing."""
    token = " "

    def execute(self):
        pass


class AimCommand(Command):
    dx,dy = 0,0

    def execute(self):
        self.interpreter.lexer.dx = self.dx
        self.interpreter.lexer.dy = self.dy


class HeadRight(AimCommand):
    """Start moving right."""
    token = ">"
    dx,dy = 1,0


class HeadLeft(AimCommand):
    """Start moving left."""
    token = "<"
    dx,dy = -1,0


class HeadUp(AimCommand):
    """Start moving up."""
    token = "^"
    dx,dy = 0,-1


class HeadDown(AimCommand):
    """Start moving down."""    
    token = "v"
    dx, dy = 0,1


class BinaryOperator(Command):

    def operate(self,a,b):
        raise NotImplementedError

    def execute(self):
        a, b = self.interpreter.pop2()
        self.interpreter.push(self.operate(a,b))


class Plus(BinaryOperator):
    """Addition: Pop `a` and `b`, then push `a+b`."""
    token = "+"

    def operate(self, a, b):
        return a+b


class Minus(BinaryOperator):
    """Subtraction: Pop `a` and `b`, then push `b-a`."""
    token = "-"

    def operate(self, a, b):
        return b-a


class Multiply(BinaryOperator):
    """Multiplication: Pop `a` and `b`, then push `a*b`"""
    token = "*"

    def operate(self, a, b):
        return a*b


class Div(BinaryOperator):
    """Integer division: Pop `a` and `b`, then push `b/a`, rounded down.
    If `a` is zero, push zero."""
    token = '/'

    def operate(self,a,b):
        return 0 if a == 0 else b // a


class GreaterThan(BinaryOperator):
    """Greater than: Pop `a` and `b`, then push 1 if b>a, otherwise push zero."""
    token = '`'

    def operate(self, a, b):
        return 1 if b > a else 0


class Mod(BinaryOperator):
    """Modulo: Pop `a` and `b`, then push `b%a`. If `a` is zero, push zero."""
    token = '%'

    def operate(self,a,b):
        return 0 if a == 0 else b % a


class UnaryOperator(Command):

    def operate(self,a):
        raise NotImplementedError

    def execute(self):
        self.interpreter.push(self.operate(self.interpreter.pop()))


class Not(UnaryOperator):
    """Logical NOT: Pop a value. If the value is zero, push `1`; otherwise, push zero."""
    token = '!'

    def operate(self,a):
        return 1 if a == 0 else 0 


class OutputCommand(Command):
    """Abstract output command"""
    format_string = None

    def execute(self):
        self.interpreter.output(self.format_string.format(self.interpreter.pop()))


class OutputInteger(OutputCommand):
    """Pop value and output as an integer."""
    token = '.'
    format_string = "{:d}"


class OutputAscii(OutputCommand):
    """Pop value and output the ASCII character represented by the integer code that is stored in the value."""
    token = ','
    format_string = "{:c}"


class Duplicate(Command):
    """Duplicate value on top of the stack. If there is nothing on top of the stack, push a 0."""
    token = ':'

    def execute(self):
        try:
            value = self.interpreter.peek()
        except IndexError:
            value = 0
        self.interpreter.push(value)


class ChooseHorizontalDirection(Command):
    """Pop a value; move right if the value is zero, left otherwise."""
    token = "_"

    def execute(self):
        value = self.interpreter.pop()
        command_class = HeadRight if value == 0 else HeadLeft
        command_class(self.interpreter).execute()


class ChooseVerticalDirection(Command):
    """Pop a value; move up if the value is zero, down otherwise."""
    token = "|"

    def execute(self):
        value = self.interpreter.pop()
        command_class = HeadDown if value == 0 else HeadUp
        command_class(self.interpreter).execute()


class ChooseRandomDirection(Command):
    """Start moving in a random cardinal direction."""
    token = '?'

    def execute(self):
        command_class = random.choice([HeadLeft,HeadRight,HeadUp,HeadDown])
        command_class(self.interpreter).execute()


class Swap(Command):
    """Swap two values on top of the stack."""
    token = '\\'

    def execute(self):
        last = self.interpreter.pop()
        try:
            penultimate = self.interpreter.pop()
        except IndexError:
            penultimate = 0
        self.interpreter.push(last)
        self.interpreter.push(penultimate)


class Discard(Command):
    """Pop a value from the stack and discard it."""
    token = "$"

    def execute(self):
        self.interpreter.pop()


class Skip(Command):
    """"Trampoline" or "Bridge": Skip next cell in the current direction."""
    token = "#"

    def execute(self):
        self.interpreter.lexer.advance()


class Put(Command):
    """A "put" call (a way to store a value for later use). 
    
    Pop y, x and v, then change the character at the position (x,y) in the
    program to the character with ASCII value v.
    """
    token = 'p'

    def execute(self):
        y, x, = self.interpreter.pop2()
        v = self.interpreter.pop()
        self.interpreter.lexer.program[y][x] = chr(v)

class Get(Command):
    """A "get" call (a way to retrieve data in storage). 
    
    Pop y and x, then push ASCII value of the character at that position in the
    program."""
    token = 'g'

    def execute(self):
        y, x = self.interpreter.pop2()
        value = self.interpreter.lexer.program[y][x]
        self.interpreter.push(ord(value))


class End(Command):
    """End program."""
    token = '@'

    def execute(self):
        # The command can't actually end the program;
        # we rely on the interpreter to see the command and halt.
        pass


###########
# Parsing #
###########
class Parser:
    """A parser of Befunge tokens"""
    interpreter = None
    commands = None

    def __init__(self,interpreter):
        self.interpreter = interpreter
        self.commands = Command.dict()

    def get_command(self,token):
        """convert a token to a command"""
        if token.value in self.commands:
            return self.commands[token.value](self.interpreter)
        else:
            return NoopCommand(self.interpreter)


class BefungeInterpreter:
    """An interpreter for the Befunge language"""

    lexer = None
    parser = None
    _data = None
    _output = None

    def __init__(self):
        self.lexer = Lexer()
        self.parser = Parser(self)
        self._data = []
        self._output = []


    def pop(self):
        """Pop a value off the data stack and return it."""
        return self._data.pop()


    def pop2(self):
        """Pop two values off the data stack and return them
        (in pop order)."""
        return self._data.pop(), self._data.pop()


    def push(self,value):
        """Push a value onto the data stack."""
        self._data.append(value)


    def peek(self):
        """Return the last value on the data stack (without popping it)."""
        return self._data[-1]


    def output(self,value):
        """Output a value."""
        self._output.append(value)

    def interpret(self,str):
        """Interpret the string *str* as a Befunge program."""
        logging.info("Hello, world!")
        self.lexer.read(str)
        logging.debug("program", self.lexer.program)
        for token in self.lexer.tokens():
            logging.debug("Token: {}".format(token))
            if isinstance(token,DigitToken):
                self.push(token.value)
            elif isinstance(token,StringToken):
                self.push(ord(token.value))
            elif isinstance(token,CommandToken):
                command = self.parser.get_command(token)
                logging.debug("command: {}".format(command))
                if isinstance(command,End):
                    logging.info("End command found.  Stack = {}".format(self._data))
                    break
                else:
                    command.execute()
            elif isinstance(token,EofToken):
                logging.info("End of file.  Stack = {}".format(self._data))
        return "".join(self._output)


def interpret(str):
    """Create a new intepreter and interpret *str*"""
    return BefungeInterpreter().interpret(str)

if __name__ == '__main__':
    import codewars_test as test
    logging.basicConfig(level=logging.DEBUG)
    # test.assert_equals(interpret('123...'),'321')   
    # test.assert_equals(interpret('>987v>.v\nv456<  :\n>321 ^ _@'), '123456789')
    # test.assert_equals(interpret(""">25*"!dlroW olleH":v
    #             v:,_@
    #             >  ^"""),'Hello World!\n')
    test.assert_equals(interpret("""08>:1-:v v *_$.@ 
  ^    _$>\:^"""),'40320')

