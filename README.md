# LipVM

## Import the project

**Step 1:** create a Python virtual environment

```shell
python3 -m venv .venv
```

**Step 2:** activate the virtual environment

On Unix systems:
```shell
source .venv/bin/activate
```

On Windows:

```shell
.venv\Scripts\activate
```

## Generate parser and visitor for a language

**Requirements:**

- An ANTLR4 grammar file, e.g. `src/languages/Minilogo/syntax/Language.g4`.
  - For now the grammar must be named: **Language**.
  - The root parsing rule must be named **start**. 
- A Java installation, version 21 or superior.
- The `antlr-4.13.2-complete.jar` from https://www.antlr.org/download.html.

```shell
java -jar antlr-4.13.2-complete.jar -Dlanguage=Python3 src/languages/Minilogo/syntax/Language.g4 -no-listener -visitor
```

Upon the execution of this command, an AST visitor is generated: see `src/languages/Minilogo/syntax/LanguageVisitor.py`.  

## Specify the semantic of a language

Based on the generated visitor, create a `Compiler` class in the directory of your language: see `src/languages/Minilogo/Compiler.py`.

This class is expected to implement a `def compile(self, code)` method returning an instance of `Bytecode` (see at the root of the project).  

This instance of `Bytecode` should hold a list of instructions to execute.  
It is the responsibility of the language implementor to define these instructions.  
To create one language instruction, create a class that implements the `def execute(self, stack, global_variables, heap)`.   
This method defines the behavior of each of the language instruction.
The method parameters represent:
- **stack**: the underlying interpreter stack (instance of `Stack`)
- **global_variables**: the global variables of the program
- **heap**: the long term memory space

## Try Minilogo

To start the currently implemented LipVM with Minilogo, execute the following command:

```shell
python -m src.languages.minilogo.ide.Minilogo
```

## Debug

To debug, for now I use `debugpy` using the following command taking `file.logo` (a logo code file) in argument:

```shell
python -m debugpy --wait-for-client --listen 5678 LipVM.py file.logo
```

Using VSCode you can use the following `launch.json` configuration to connect to the debugging session:

```json
{
  "version": "0.2.0",
  "configurations": [
      {
          "name": "Python Debugger: Remote Attach",
          "type": "debugpy",
          "request": "attach",
          "connect": {
              "host": "localhost",
              "port": 5678
          }
      }
  ]
}
```
