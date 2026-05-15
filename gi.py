#!/usr/bin/env python3
"""
───────────────────────────────────────────────────────────────────────────────
                                GI — GLANG INTERPRETER
───────────────────────────────────────────────────────────────────────────────

Inspired By:
    • Python
    • Lua
    • C

Overview:
    GI (GLANG Interpreted) is a lightweight interpreted programming language
    focused on simplicity, performance, and low-level system access.

    It combines:
        • Python-style readability
        • Lua-like scripting flexibility
        • C-level power and control

Purpose:
    GI is designed for:
        • Graphics programming
        • System manipulation
        • General software development
        • Low-level and kernel-oriented utilities
        • Sandboxed native execution through Clang integration

Goals:
    • Easy-to-read syntax
    • Fast interpreted execution
    • Direct system interaction
    • Expandable standard library
    • Native module support
    • Safe but powerful runtime environment

Core Philosophy:
    "Readable scripting with native-level capability."

Runtime Notes:
    • Interpreted execution model
    • Planned sandboxed Clang backend
    • Designed to support native library loading
    • Cross-platform architecture planned

File:
    gi.py — Main interpreter/runtime entry point
───────────────────────────────────────────────────────────────────────────────
"""

import sys
import re
import os
import ctypes
import math
import time
import json
import random

# ─────────────────────────────────────────────
#  TOKENS
# ─────────────────────────────────────────────

TK = {
    # literals
    'NUMBER':'NUMBER','STRING':'STRING','BOOL':'BOOL','NULL':'NULL',
    # idents / keywords
    'IDENT':'IDENT',
    'LET':'let','IF':'if','ELSE':'else','ELIF':'elif',
    'WHILE':'while','FOR':'for','IN':'in',
    'FUNC':'func','RETURN':'return',
    'PASS':'pass','CONTINUE':'continue','BREAK':'break',
    'WITH':'with','AS':'as',
    'CLASS':'class','NEW':'new',
    'IMPORT':'import',
    'TRUE':'true','FALSE':'false','NULL_KW':'null',
    # ops
    'PLUS':'+','MINUS':'-','STAR':'*','SLASH':'/','PERCENT':'%','STARSTAR':'**',
    'EQ':'==','NEQ':'!=','LT':'<','GT':'>','LTE':'<=','GTE':'>=',
    'AND':'&&','OR':'||','NOT':'!',
    'ASSIGN':'=','PLUSEQ':'+=','MINUSEQ':'-=','STAREQ':'*=','SLASHEQ':'/=',
    # delimiters
    'LPAREN':'(','RPAREN':')','LBRACE':'{','RBRACE':'}','LBRACK':'[','RBRACK':']',
    'COMMA':',','DOT':'.','SEMI':';','COLON':':',
    'ARROW':'->',
    'EOF':'EOF',
}

KEYWORDS = {
    'let','if','else','elif','while','for','in','func','return',
    'pass','continue','break','with','as','class','new','import',
    'true','false','null','and','or','not',
}

class Token:
    def __init__(self, kind, value, line):
        self.kind  = kind
        self.value = value
        self.line  = line
    def __repr__(self):
        return f'Token({self.kind}, {self.value!r}, L{self.line})'

# ─────────────────────────────────────────────
#  LEXER
# ─────────────────────────────────────────────

class LexError(Exception): pass

class Lexer:
    def __init__(self, src):
        self.src  = src
        self.pos  = 0
        self.line = 1

    def peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else ''

    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == '\n': self.line += 1
        return ch

    def match(self, ch):
        if self.pos < len(self.src) and self.src[self.pos] == ch:
            self.pos += 1
            return True
        return False

    def skip_ws_and_comments(self):
        while self.pos < len(self.src):
            ch = self.peek()
            if ch in ' \t\r\n':
                self.advance()
            elif ch == '/' and self.peek(1) == '/':
                while self.pos < len(self.src) and self.peek() != '\n':
                    self.advance()
            elif ch == '/' and self.peek(1) == '*':
                self.advance(); self.advance()
                while self.pos < len(self.src):
                    if self.peek() == '*' and self.peek(1) == '/':
                        self.advance(); self.advance(); break
                    self.advance()
            else:
                break

    def read_string(self, quote):
        self.advance()  # opening quote
        buf = []
        while self.pos < len(self.src):
            ch = self.peek()
            if ch == '\\':
                self.advance()
                esc = self.advance()
                buf.append({'n':'\n','t':'\t','r':'\r','\\':'\\',
                            '"':'"',"'":'\'','0':'\0'}.get(esc, esc))
            elif ch == quote:
                self.advance()
                break
            else:
                buf.append(self.advance())
        return ''.join(buf)

    def tokenize(self):
        tokens = []
        while True:
            self.skip_ws_and_comments()
            if self.pos >= len(self.src):
                tokens.append(Token('EOF','',self.line))
                break
            ln = self.line
            ch = self.peek()

            # string
            if ch in ('"', "'"):
                s = self.read_string(ch)
                tokens.append(Token('STRING', s, ln))
                continue

            # number
            if ch.isdigit() or (ch == '.' and self.peek(1).isdigit()):
                buf = []
                while self.pos < len(self.src) and (self.peek().isdigit() or self.peek() == '.'):
                    buf.append(self.advance())
                raw = ''.join(buf)
                val = float(raw) if '.' in raw else int(raw)
                tokens.append(Token('NUMBER', val, ln))
                continue

            # ident / keyword
            if ch.isalpha() or ch == '_':
                buf = []
                while self.pos < len(self.src) and (self.peek().isalnum() or self.peek() == '_'):
                    buf.append(self.advance())
                word = ''.join(buf)
                if word == 'true':  tokens.append(Token('BOOL', True, ln))
                elif word == 'false': tokens.append(Token('BOOL', False, ln))
                elif word == 'null':  tokens.append(Token('NULL', None, ln))
                elif word == 'and':   tokens.append(Token('AND', '&&', ln))
                elif word == 'or':    tokens.append(Token('OR', '||', ln))
                elif word == 'not':   tokens.append(Token('NOT', '!', ln))
                elif word in KEYWORDS: tokens.append(Token(word.upper(), word, ln))
                else: tokens.append(Token('IDENT', word, ln))
                continue

            # two-char ops
            two = ch + self.peek(1)
            two_map = {
                '**':'STARSTAR','==':'EQ','!=':'NEQ','<=':'LTE','>=':'GTE',
                '&&':'AND','||':'OR','+=':'PLUSEQ','-=':'MINUSEQ',
                '*=':'STAREQ','/=':'SLASHEQ','->':'ARROW',
            }
            if two in two_map:
                self.advance(); self.advance()
                tokens.append(Token(two_map[two], two, ln))
                continue

            # single-char
            one_map = {
                '+':'PLUS','-':'MINUS','*':'STAR','/':'SLASH','%':'PERCENT',
                '=':'ASSIGN','<':'LT','>':'GT','!':'NOT',
                '(':'LPAREN',')':'RPAREN','{':'LBRACE','}':'RBRACE',
                '[':'LBRACK',']':'RBRACK',',':'COMMA','.':'DOT',
                ';':'SEMI',':':'COLON',
            }
            if ch in one_map:
                self.advance()
                tokens.append(Token(one_map[ch], ch, ln))
                continue

            raise LexError(f"Unexpected character {ch!r} at line {ln}")

        return tokens

# ─────────────────────────────────────────────
#  AST NODES
# ─────────────────────────────────────────────

class Node:
    pass

class Block(Node):
    def __init__(self, stmts): self.stmts = stmts

class LetStmt(Node):
    def __init__(self, name, value, line): self.name=name; self.value=value; self.line=line

class AssignStmt(Node):
    def __init__(self, target, op, value, line): self.target=target; self.op=op; self.value=value; self.line=line

class IfStmt(Node):
    def __init__(self, branches, else_block):
        self.branches = branches   # list of (cond, block)
        self.else_block = else_block

class WhileStmt(Node):
    def __init__(self, cond, body): self.cond=cond; self.body=body

class ForStmt(Node):
    def __init__(self, var, iterable, body): self.var=var; self.iterable=iterable; self.body=body

class FuncDef(Node):
    def __init__(self, name, params, body, line): self.name=name; self.params=params; self.body=body; self.line=line

class ReturnStmt(Node):
    def __init__(self, value, line): self.value=value; self.line=line

class PassStmt(Node): pass
class ContinueStmt(Node): pass
class BreakStmt(Node): pass

class WithStmt(Node):
    def __init__(self, call, alias, body): self.call=call; self.alias=alias; self.body=body

class ClassDef(Node):
    def __init__(self, name, base, body): self.name=name; self.base=base; self.body=body

class ImportStmt(Node):
    def __init__(self, path, alias): self.path=path; self.alias=alias

class ExprStmt(Node):
    def __init__(self, expr): self.expr=expr

# Expressions
class NumberLit(Node):
    def __init__(self, v): self.v=v
class StringLit(Node):
    def __init__(self, v): self.v=v
class BoolLit(Node):
    def __init__(self, v): self.v=v
class NullLit(Node): pass
class Ident(Node):
    def __init__(self, name, line): self.name=name; self.line=line
class BinOp(Node):
    def __init__(self, op, left, right): self.op=op; self.left=left; self.right=right
class UnaryOp(Node):
    def __init__(self, op, expr): self.op=op; self.expr=expr
class Call(Node):
    def __init__(self, callee, args, line): self.callee=callee; self.args=args; self.line=line
class GetAttr(Node):
    def __init__(self, obj, attr, line): self.obj=obj; self.attr=attr; self.line=line
class SetAttr(Node):
    def __init__(self, obj, attr, value): self.obj=obj; self.attr=attr; self.value=value
class Index(Node):
    def __init__(self, obj, idx, line): self.obj=obj; self.idx=idx; self.line=line
class SetIndex(Node):
    def __init__(self, obj, idx, value): self.obj=obj; self.idx=idx; self.value=value
class ListLit(Node):
    def __init__(self, items): self.items=items
class DictLit(Node):
    def __init__(self, pairs): self.pairs=pairs  # list of (key_expr, val_expr)
class NewExpr(Node):
    def __init__(self, cls, args, line): self.cls=cls; self.args=args; self.line=line
class LambdaExpr(Node):
    def __init__(self, params, body): self.params=params; self.body=body

# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

class ParseError(Exception): pass

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos    = 0

    def peek(self, offset=0):
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def advance(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def check(self, *kinds):
        return self.peek().kind in kinds

    def match(self, *kinds):
        if self.check(*kinds):
            return self.advance()
        return None

    def expect(self, kind, msg=None):
        if self.peek().kind == kind:
            return self.advance()
        t = self.peek()
        raise ParseError(msg or f"Expected {kind!r}, got {t.kind!r} ({t.value!r}) at line {t.line}")

    def parse(self):
        stmts = []
        while not self.check('EOF'):
            stmts.append(self.parse_stmt())
        return Block(stmts)

    def parse_block(self):
        self.expect('LBRACE')
        stmts = []
        while not self.check('RBRACE','EOF'):
            stmts.append(self.parse_stmt())
        self.expect('RBRACE')
        return Block(stmts)

    def parse_stmt(self):
        self.match('SEMI')  # optional semicolons
        t = self.peek()

        if t.kind == 'LET':      return self.parse_let()
        if t.kind == 'IF':       return self.parse_if()
        if t.kind == 'WHILE':    return self.parse_while()
        if t.kind == 'FOR':      return self.parse_for()
        if t.kind == 'FUNC':     return self.parse_func()
        if t.kind == 'RETURN':   return self.parse_return()
        if t.kind == 'PASS':     self.advance(); return PassStmt()
        if t.kind == 'CONTINUE': self.advance(); return ContinueStmt()
        if t.kind == 'BREAK':    self.advance(); return BreakStmt()
        if t.kind == 'WITH':     return self.parse_with()
        if t.kind == 'CLASS':    return self.parse_class()
        if t.kind == 'IMPORT':   return self.parse_import()

        # assignment or expression
        return self.parse_assign_or_expr()

    def parse_let(self):
        ln = self.peek().line
        self.expect('LET')
        name = self.expect('IDENT').value
        self.expect('ASSIGN')
        val = self.parse_expr()
        self.match('SEMI')
        return LetStmt(name, val, ln)

    def parse_assign_or_expr(self):
        expr = self.parse_expr()
        op_map = {'ASSIGN':'=','PLUSEQ':'+=','MINUSEQ':'-=','STAREQ':'*=','SLASHEQ':'/='}
        if self.peek().kind in op_map:
            op = op_map[self.advance().kind]
            val = self.parse_expr()
            self.match('SEMI')
            if isinstance(expr, Ident):
                return AssignStmt(expr.name, op, val, expr.line)
            if isinstance(expr, GetAttr):
                return SetAttr(expr.obj, expr.attr, val)
            if isinstance(expr, Index):
                return SetIndex(expr.obj, expr.idx, val)
            raise ParseError("Invalid assignment target")
        self.match('SEMI')
        return ExprStmt(expr)

    def parse_if(self):
        self.expect('IF')
        self.expect('LPAREN')
        cond = self.parse_expr()
        self.expect('RPAREN')
        body = self.parse_block()
        branches = [(cond, body)]
        else_block = None
        while self.check('ELIF'):
            self.advance()
            self.expect('LPAREN')
            c2 = self.parse_expr()
            self.expect('RPAREN')
            b2 = self.parse_block()
            branches.append((c2, b2))
        if self.match('ELSE'):
            else_block = self.parse_block()
        return IfStmt(branches, else_block)

    def parse_while(self):
        self.expect('WHILE')
        self.expect('LPAREN')
        cond = self.parse_expr()
        self.expect('RPAREN')
        body = self.parse_block()
        return WhileStmt(cond, body)

    def parse_for(self):
        self.expect('FOR')
        self.expect('LPAREN')
        var = self.expect('IDENT').value
        self.expect('IN')
        iterable = self.parse_expr()
        self.expect('RPAREN')
        body = self.parse_block()
        return ForStmt(var, iterable, body)

    def parse_func(self):
        ln = self.peek().line
        self.expect('FUNC')
        name = self.expect('IDENT').value
        self.expect('LPAREN')
        params = []
        while not self.check('RPAREN','EOF'):
            params.append(self.expect('IDENT').value)
            if not self.match('COMMA'):
                break
        self.expect('RPAREN')
        body = self.parse_block()
        return FuncDef(name, params, body, ln)

    def parse_return(self):
        ln = self.peek().line
        self.expect('RETURN')
        val = None
        if not self.check('SEMI','RBRACE','EOF'):
            val = self.parse_expr()
        self.match('SEMI')
        return ReturnStmt(val, ln)

    def parse_with(self):
        self.expect('WITH')
        self.expect('LPAREN')
        call = self.parse_expr()
        self.expect('RPAREN')
        self.expect('AS')
        alias = self.expect('IDENT').value
        body = self.parse_block()
        return WithStmt(call, alias, body)

    def parse_class(self):
        self.expect('CLASS')
        name = self.expect('IDENT').value
        base = None
        if self.match('LPAREN'):
            base = self.expect('IDENT').value
            self.expect('RPAREN')
        body = self.parse_block()
        return ClassDef(name, base, body)

    def parse_import(self):
        self.expect('IMPORT')
        parts = [self.expect('IDENT').value]
        while self.match('DOT'):
            parts.append(self.expect('IDENT').value)
        alias = None
        if self.match('AS'):
            alias = self.expect('IDENT').value
        self.match('SEMI')
        return ImportStmt('.'.join(parts), alias)

    # ── expressions ──────────────────────────

    def parse_expr(self): return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.check('OR'):
            op = self.advance().value
            left = BinOp('||', left, self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self.check('AND'):
            op = self.advance().value
            left = BinOp('&&', left, self.parse_equality())
        return left

    def parse_equality(self):
        left = self.parse_comparison()
        while self.check('EQ','NEQ'):
            op = self.advance().value
            left = BinOp(op, left, self.parse_comparison())
        return left

    def parse_comparison(self):
        left = self.parse_add()
        while self.check('LT','GT','LTE','GTE'):
            op = self.advance().value
            left = BinOp(op, left, self.parse_add())
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.check('PLUS','MINUS'):
            op = self.advance().value
            left = BinOp(op, left, self.parse_mul())
        return left

    def parse_mul(self):
        left = self.parse_power()
        while self.check('STAR','SLASH','PERCENT'):
            op = self.advance().value
            left = BinOp(op, left, self.parse_power())
        return left

    def parse_power(self):
        left = self.parse_unary()
        if self.check('STARSTAR'):
            self.advance()
            right = self.parse_power()
            return BinOp('**', left, right)
        return left

    def parse_unary(self):
        if self.check('NOT','MINUS'):
            op = self.advance().value
            return UnaryOp(op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            if self.check('DOT'):
                ln = self.peek().line
                self.advance()
                attr = self.expect('IDENT').value
                if self.check('LPAREN'):
                    args = self.parse_arglist()
                    expr = Call(GetAttr(expr, attr, ln), args, ln)
                else:
                    expr = GetAttr(expr, attr, ln)
            elif self.check('LPAREN'):
                ln = self.peek().line
                args = self.parse_arglist()
                expr = Call(expr, args, ln)
            elif self.check('LBRACK'):
                ln = self.peek().line
                self.advance()
                idx = self.parse_expr()
                self.expect('RBRACK')
                expr = Index(expr, idx, ln)
            else:
                break
        return expr

    def parse_arglist(self):
        self.expect('LPAREN')
        args = []
        while not self.check('RPAREN','EOF'):
            args.append(self.parse_expr())
            if not self.match('COMMA'): break
        self.expect('RPAREN')
        return args

    def parse_primary(self):
        t = self.peek()
        if t.kind == 'NUMBER': self.advance(); return NumberLit(t.value)
        if t.kind == 'STRING': self.advance(); return StringLit(t.value)
        if t.kind == 'BOOL':   self.advance(); return BoolLit(t.value)
        if t.kind == 'NULL':   self.advance(); return NullLit()
        if t.kind == 'IDENT':  self.advance(); return Ident(t.value, t.line)
        if t.kind == 'NEW':
            self.advance()
            cls = self.expect('IDENT').value
            args = self.parse_arglist()
            return NewExpr(cls, args, t.line)
        if t.kind == 'LPAREN':
            self.advance()
            e = self.parse_expr()
            self.expect('RPAREN')
            return e
        if t.kind == 'LBRACK':
            self.advance()
            items = []
            while not self.check('RBRACK','EOF'):
                items.append(self.parse_expr())
                if not self.match('COMMA'): break
            self.expect('RBRACK')
            return ListLit(items)
        if t.kind == 'LBRACE':
            self.advance()
            pairs = []
            while not self.check('RBRACE','EOF'):
                k = self.parse_expr()
                self.expect('COLON')
                v = self.parse_expr()
                pairs.append((k,v))
                if not self.match('COMMA'): break
            self.expect('RBRACE')
            return DictLit(pairs)
        if t.kind == 'FUNC':
            self.advance()
            self.expect('LPAREN')
            params = []
            while not self.check('RPAREN','EOF'):
                params.append(self.expect('IDENT').value)
                if not self.match('COMMA'): break
            self.expect('RPAREN')
            if self.check('ARROW'):
                self.advance()
                body = self.parse_expr()
            else:
                body = self.parse_block()
            return LambdaExpr(params, body)
        raise ParseError(f"Unexpected token {t.kind!r} ({t.value!r}) at line {t.line}")

# ─────────────────────────────────────────────
#  RUNTIME VALUES
# ─────────────────────────────────────────────

class GIFunction:
    def __init__(self, name, params, body, closure):
        self.name=name; self.params=params; self.body=body; self.closure=closure
    def __repr__(self): return f'<func {self.name}>'

class GIClass:
    def __init__(self, name, base, methods, env):
        self.name=name; self.base=base; self.methods=methods; self.env=env
    def __repr__(self): return f'<class {self.name}>'

class GIInstance:
    def __init__(self, klass):
        self.klass=klass; self.fields={}
    def get(self, name):
        if name in self.fields: return self.fields[name]
        k = self.klass
        while k:
            if name in k.methods: return BoundMethod(self, k.methods[name])
            k = k.base
        raise RuntimeError(f"No attribute '{name}' on {self.klass.name}")
    def set(self, name, val): self.fields[name]=val
    def __repr__(self): return f'<{self.klass.name} instance>'

class BoundMethod:
    def __init__(self, instance, func): self.instance=instance; self.func=func
    def __repr__(self): return f'<bound method {self.func.name}>'

class GIFile:
    def __init__(self, fh, mode): self.fh=fh; self.mode=mode
    def __repr__(self): return f'<file {self.fh.name!r}>'

class GILib:
    def __init__(self, name, lib): self.name=name; self.lib=lib
    def __repr__(self): return f'<lib {self.name!r}>'

# ─────────────────────────────────────────────
#  SIGNALS
# ─────────────────────────────────────────────

class ReturnSignal(Exception):
    def __init__(self, val): self.val=val
class ContinueSignal(Exception): pass
class BreakSignal(Exception): pass

# ─────────────────────────────────────────────
#  ENVIRONMENT
# ─────────────────────────────────────────────

class Env:
    def __init__(self, parent=None):
        self.vars   = {}
        self.parent = parent

    def get(self, name, line=None):
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name, line)
        raise RuntimeError(f"Undefined variable '{name}'" + (f" at line {line}" if line else ""))

    def set(self, name, val):
        if name in self.vars: self.vars[name]=val; return
        if self.parent and self.parent.has(name):
            self.parent.set(name, val); return
        # new binding at current scope
        self.vars[name]=val

    def define(self, name, val):
        self.vars[name]=val

    def has(self, name):
        if name in self.vars: return True
        if self.parent: return self.parent.has(name)
        return False

# ─────────────────────────────────────────────
#  INTERPRETER
# ─────────────────────────────────────────────

class RuntimeError_(Exception): pass

def gi_str(val):
    if val is None: return "null"
    if val is True: return "true"
    if val is False: return "false"
    if isinstance(val, float) and val == int(val): return str(int(val))
    if isinstance(val, list): return "[" + ", ".join(gi_str(v) for v in val) + "]"
    if isinstance(val, dict): return "{" + ", ".join(f"{gi_str(k)}: {gi_str(v)}" for k,v in val.items()) + "}"
    return str(val)

class Interpreter:
    def __init__(self):
        self.globals = Env()
        self._setup_builtins()

    def _setup_builtins(self):
        g = self.globals

        # I/O
        g.define('printl',  lambda *a: print(' '.join(gi_str(x) for x in a)))
        g.define('print',   lambda *a: print(' '.join(gi_str(x) for x in a), end=''))
        g.define('readl',   lambda prompt='': input(prompt))
        g.define('read',    lambda: sys.stdin.read())

        # Type coercion
        g.define('int',    lambda x: int(x))
        g.define('float',  lambda x: float(x))
        g.define('str',    lambda x: gi_str(x))
        g.define('bool',   lambda x: bool(x))
        g.define('type',   lambda x: type(x).__name__)

        # Math
        g.define('math', {
            'abs':   lambda x: abs(x),
            'sqrt':  lambda x: math.sqrt(x),
            'floor': lambda x: math.floor(x),
            'ceil':  lambda x: math.ceil(x),
            'round': lambda x,n=0: round(x,n),
            'pi':    math.pi,
            'e':     math.e,
            'pow':   lambda x,y: x**y,
            'min':   lambda *a: min(*a),
            'max':   lambda *a: max(*a),
            'sin':   math.sin,'cos':math.cos,'tan':math.tan,
            'log':   math.log,'log10':math.log10,
            'random':random.random,
            'randint':random.randint,
        })

        # String methods
        g.define('strlen',    lambda s: len(s))
        g.define('substr',    lambda s,a,b: s[a:b])
        g.define('split',     lambda s,d=' ': s.split(d))
        g.define('join',      lambda d,lst: d.join(gi_str(x) for x in lst))
        g.define('trim',      lambda s: s.strip())
        g.define('upper',     lambda s: s.upper())
        g.define('lower',     lambda s: s.lower())
        g.define('contains',  lambda s,sub: sub in s)
        g.define('replace',   lambda s,a,b: s.replace(a,b))
        g.define('startswith',lambda s,p: s.startswith(p))
        g.define('endswith',  lambda s,p: s.endswith(p))
        g.define('format',    lambda s,*a: s.format(*a))

        # List / collection
        g.define('len',     lambda x: len(x))
        g.define('push',    lambda lst,v: lst.append(v))
        g.define('pop',     lambda lst: lst.pop())
        g.define('insert',  lambda lst,i,v: lst.insert(i,v))
        g.define('remove',  lambda lst,v: lst.remove(v))
        g.define('reverse', lambda lst: lst.reverse())
        g.define('sort',    lambda lst: lst.sort())
        g.define('slice',   lambda lst,a,b: lst[a:b])
        g.define('map',     lambda f,lst: [self._call_value(f,[x],0) for x in lst])
        g.define('filter',  lambda f,lst: [x for x in lst if self._call_value(f,[x],0)])
        g.define('reduce',  lambda f,lst,init=None: self._reduce(f,lst,init))
        g.define('range',   lambda *a: list(range(*[int(x) for x in a])))
        g.define('keys',    lambda d: list(d.keys()))
        g.define('values',  lambda d: list(d.values()))
        g.define('items',   lambda d: [[k,v] for k,v in d.items()])
        g.define('haskey',  lambda d,k: k in d)
        g.define('delkey',  lambda d,k: d.pop(k,None))

        # OS / sys
        g.define('exit',    lambda code=0: sys.exit(code))
        g.define('args',    sys.argv[1:])
        g.define('getenv',  lambda k,d=None: os.environ.get(k,d))
        g.define('setenv',  lambda k,v: os.environ.__setitem__(k,v))
        g.define('getcwd',  lambda: os.getcwd())
        g.define('listdir', lambda p='.': os.listdir(p))
        g.define('exists',  lambda p: os.path.exists(p))
        g.define('isfile',  lambda p: os.path.isfile(p))
        g.define('isdir',   lambda p: os.path.isdir(p))
        g.define('mkdir',   lambda p: os.makedirs(p, exist_ok=True))
        g.define('remove_file', lambda p: os.remove(p))
        g.define('sleep',   lambda s: time.sleep(s))
        g.define('time',    lambda: time.time())
        g.define('clock',   lambda: time.perf_counter())

        # JSON
        g.define('json', {
            'parse':  lambda s: json.loads(s),
            'stringify': lambda v, indent=None: json.dumps(v, indent=indent),
        })

        # with-compatible open
        def gi_open(path, mode='r'):
            try:
                fh = open(path, mode)
                return GIFile(fh, mode)
            except Exception as e:
                raise RuntimeError_(str(e))
        g.define('file', gi_open)

        # loadlib
        def gi_loadlib(name):
            try:
                if sys.platform == 'win32':
                    lib = ctypes.WinDLL(name)
                else:
                    lib = ctypes.CDLL(name)
                return GILib(name, lib)
            except Exception as e:
                raise RuntimeError_(f"loadlib failed: {e}")
        g.define('loadlib', gi_loadlib)

        # assert / error
        g.define('assert', lambda cond, msg="Assertion failed": (_ for _ in ()).throw(RuntimeError_(msg)) if not cond else None)
        g.define('error',  lambda msg: (_ for _ in ()).throw(RuntimeError_(msg)))
        g.define('typeof', lambda x: self._typeof(x))

    def _typeof(self, x):
        if x is None: return 'null'
        if isinstance(x, bool): return 'bool'
        if isinstance(x, (int,float)): return 'number'
        if isinstance(x, str): return 'string'
        if isinstance(x, list): return 'list'
        if isinstance(x, dict): return 'dict'
        if isinstance(x, GIFunction): return 'func'
        if isinstance(x, GIClass): return 'class'
        if isinstance(x, GIInstance): return x.klass.name
        if isinstance(x, GIFile): return 'file'
        if isinstance(x, GILib): return 'lib'
        return 'unknown'

    def _reduce(self, f, lst, init):
        acc = init if init is not None else lst[0]
        for x in (lst if init is not None else lst[1:]):
            acc = self._call_value(f, [acc, x], 0)
        return acc

    def run(self, node, env=None):
        if env is None: env = self.globals
        return self.exec_block(node, env)

    def exec_block(self, block, env):
        # Lambda bodies can be a bare expression node (arrow syntax)
        if not isinstance(block, Block):
            raise ReturnSignal(self.eval_expr(block, env))
        result = None
        for stmt in block.stmts:
            result = self.exec_stmt(stmt, env)
        return result

    def exec_stmt(self, node, env):
        if isinstance(node, LetStmt):
            val = self.eval_expr(node.value, env)
            env.define(node.name, val)

        elif isinstance(node, AssignStmt):
            val = self.eval_expr(node.value, env)
            if node.op != '=':
                cur = env.get(node.target, node.line)
                if node.op == '+=': val = self._add(cur, val)
                elif node.op == '-=': val = cur - val
                elif node.op == '*=': val = cur * val
                elif node.op == '/=': val = cur / val
            env.set(node.target, val)

        elif isinstance(node, SetAttr):
            obj = self.eval_expr(node.obj, env)
            val = self.eval_expr(node.value, env)
            if isinstance(obj, GIInstance): obj.set(node.attr, val)
            elif isinstance(obj, dict): obj[node.attr] = val
            else: raise RuntimeError_(f"Cannot set attribute on {type(obj).__name__}")

        elif isinstance(node, SetIndex):
            obj = self.eval_expr(node.obj, env)
            idx = self.eval_expr(node.idx, env)
            val = self.eval_expr(node.value, env)
            obj[idx] = val

        elif isinstance(node, IfStmt):
            for cond, body in node.branches:
                if self.eval_expr(cond, env):
                    inner = Env(env)
                    self.exec_block(body, inner)
                    return
            if node.else_block:
                inner = Env(env)
                self.exec_block(node.else_block, inner)

        elif isinstance(node, WhileStmt):
            while self.eval_expr(node.cond, env):
                inner = Env(env)
                try:
                    self.exec_block(node.body, inner)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break

        elif isinstance(node, ForStmt):
            iterable = self.eval_expr(node.iterable, env)
            if isinstance(iterable, dict): iterable = list(iterable.keys())
            for item in iterable:
                inner = Env(env)
                inner.define(node.var, item)
                try:
                    self.exec_block(node.body, inner)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break

        elif isinstance(node, FuncDef):
            fn = GIFunction(node.name, node.params, node.body, env)
            env.define(node.name, fn)

        elif isinstance(node, ReturnStmt):
            val = self.eval_expr(node.value, env) if node.value else None
            raise ReturnSignal(val)

        elif isinstance(node, PassStmt): pass
        elif isinstance(node, ContinueStmt): raise ContinueSignal()
        elif isinstance(node, BreakStmt):    raise BreakSignal()

        elif isinstance(node, WithStmt):
            ctx = self.eval_expr(node.call, env)
            inner = Env(env)
            inner.define(node.alias, ctx)
            try:
                self.exec_block(node.body, inner)
            finally:
                if isinstance(ctx, GIFile):
                    ctx.fh.close()

        elif isinstance(node, ClassDef):
            base = None
            if node.base:
                base = env.get(node.base)
            methods = {}
            class_env = Env(env)
            for stmt in node.body.stmts:
                if isinstance(stmt, FuncDef):
                    methods[stmt.name] = GIFunction(stmt.name, stmt.params, stmt.body, class_env)
            klass = GIClass(node.name, base, methods, class_env)
            env.define(node.name, klass)

        elif isinstance(node, ImportStmt):
            self._do_import(node, env)

        elif isinstance(node, ExprStmt):
            self.eval_expr(node.expr, env)

    def _do_import(self, node, env):
        parts = node.path.split('.')
        # try loading a .gi file
        gi_path = os.path.join(*parts) + '.gi'
        if os.path.exists(gi_path):
            with open(gi_path) as f:
                src = f.read()
            mod_env = Env(self.globals)
            tokens = Lexer(src).tokenize()
            ast    = Parser(tokens).parse()
            Interpreter._exec_in(self, ast, mod_env)
            alias = node.alias or parts[-1]
            env.define(alias, mod_env.vars)
        else:
            # try Python stdlib shim
            try:
                import importlib
                mod = importlib.import_module(node.path)
                alias = node.alias or parts[-1]
                env.define(alias, mod)
            except ImportError:
                raise RuntimeError_(f"Cannot import '{node.path}'")

    def _exec_in(self, block, env):
        self.exec_block(block, env)

    def eval_expr(self, node, env):
        if isinstance(node, NumberLit): return node.v
        if isinstance(node, StringLit): return node.v
        if isinstance(node, BoolLit):   return node.v
        if isinstance(node, NullLit):   return None
        if isinstance(node, ListLit):
            return [self.eval_expr(i, env) for i in node.items]
        if isinstance(node, DictLit):
            d = {}
            for k,v in node.pairs:
                d[self.eval_expr(k,env)] = self.eval_expr(v,env)
            return d
        if isinstance(node, Ident):
            return env.get(node.name, node.line)
        if isinstance(node, BinOp):
            return self.eval_binop(node, env)
        if isinstance(node, UnaryOp):
            v = self.eval_expr(node.expr, env)
            if node.op == '-': return -v
            if node.op in ('!','not'): return not v
        if isinstance(node, Call):
            callee = self.eval_expr(node.callee, env)
            args   = [self.eval_expr(a, env) for a in node.args]
            return self._call_value(callee, args, node.line)
        if isinstance(node, GetAttr):
            obj = self.eval_expr(node.obj, env)
            return self._get_attr(obj, node.attr, node.line)
        if isinstance(node, Index):
            obj = self.eval_expr(node.obj, env)
            idx = self.eval_expr(node.idx, env)
            try: return obj[idx]
            except (KeyError,IndexError) as e: raise RuntimeError_(str(e))
        if isinstance(node, NewExpr):
            klass = env.get(node.cls, node.line)
            args  = [self.eval_expr(a,env) for a in node.args]
            return self._instantiate(klass, args, node.line)
        if isinstance(node, LambdaExpr):
            return GIFunction('<lambda>', node.params, node.body, env)
        raise RuntimeError_(f"Unknown expr node: {type(node).__name__}")

    def _get_attr(self, obj, attr, line):
        if isinstance(obj, GIInstance):
            return obj.get(attr)
        if isinstance(obj, dict):
            if attr in obj: return obj[attr]
            raise RuntimeError_(f"Dict has no key '{attr}'")
        if isinstance(obj, GIFile):
            fh = obj.fh
            if attr == 'read':    return lambda *a: fh.read(*a)
            if attr == 'readline':return lambda: fh.readline()
            if attr == 'readlines':return lambda: fh.readlines()
            if attr == 'write':   return lambda s: fh.write(s)
            if attr == 'close':   return lambda: fh.close()
            if attr == 'name':    return fh.name
        if isinstance(obj, GILib):
            # return a ctypes function wrapper
            try:
                cfn = getattr(obj.lib, attr)
                def caller(*args):
                    c_args = []
                    for a in args:
                        if isinstance(a, int):    c_args.append(ctypes.c_long(a))
                        elif isinstance(a, float): c_args.append(ctypes.c_double(a))
                        elif isinstance(a, str):   c_args.append(ctypes.c_char_p(a.encode()))
                        else: c_args.append(a)
                    return cfn(*c_args)
                return caller
            except AttributeError:
                raise RuntimeError_(f"Library has no symbol '{attr}'")
        if isinstance(obj, list):
            methods = {
                'push':    lambda v: obj.append(v),
                'pop':     lambda: obj.pop(),
                'len':     lambda: len(obj),
                'sort':    lambda: obj.sort(),
                'reverse': lambda: obj.reverse(),
                'slice':   lambda a,b: obj[a:b],
                'join':    lambda d='': d.join(gi_str(x) for x in obj),
                'map':     lambda f: [self._call_value(f,[x],line) for x in obj],
                'filter':  lambda f: [x for x in obj if self._call_value(f,[x],line)],
                'contains':lambda v: v in obj,
                'index':   lambda v: obj.index(v),
            }
            if attr in methods: return methods[attr]
        if isinstance(obj, str):
            methods = {
                'len':        lambda: len(obj),
                'upper':      lambda: obj.upper(),
                'lower':      lambda: obj.lower(),
                'trim':       lambda: obj.strip(),
                'split':      lambda d=' ': obj.split(d),
                'replace':    lambda a,b: obj.replace(a,b),
                'contains':   lambda s: s in obj,
                'startswith': lambda p: obj.startswith(p),
                'endswith':   lambda p: obj.endswith(p),
                'find':       lambda s: obj.find(s),
                'format':     lambda *a: obj.format(*a),
                'chars':      lambda: list(obj),
            }
            if attr in methods: return methods[attr]
        # fallback: Python attr
        if hasattr(obj, attr):
            return getattr(obj, attr)
        raise RuntimeError_(f"No attribute '{attr}' on {self._typeof(obj)!r} at line {line}")

    def _call_value(self, callee, args, line):
        if callable(callee):
            try: return callee(*args)
            except RuntimeError_ as e: raise
            except Exception as e: raise RuntimeError_(str(e))
        if isinstance(callee, GIFunction):
            fn_env = Env(callee.closure)
            for i, p in enumerate(callee.params):
                fn_env.define(p, args[i] if i < len(args) else None)
            try:
                self.exec_block(callee.body, fn_env)
            except ReturnSignal as r:
                return r.val
            return None
        if isinstance(callee, BoundMethod):
            fn_env = Env(callee.func.closure)
            fn_env.define('self', callee.instance)
            for i, p in enumerate(callee.func.params[1:]):  # skip 'self'
                fn_env.define(p, args[i] if i < len(args) else None)
            try:
                self.exec_block(callee.func.body, fn_env)
            except ReturnSignal as r:
                return r.val
            return None
        if isinstance(callee, GIClass):
            return self._instantiate(callee, args, line)
        raise RuntimeError_(f"'{self._typeof(callee)}' is not callable at line {line}")

    def _instantiate(self, klass, args, line):
        inst = GIInstance(klass)
        # call init if exists
        k = klass
        while k:
            if 'init' in k.methods:
                fn_env = Env(k.methods['init'].closure)
                fn_env.define('self', inst)
                for i, p in enumerate(k.methods['init'].params[1:]):
                    fn_env.define(p, args[i] if i < len(args) else None)
                try:
                    self.exec_block(k.methods['init'].body, fn_env)
                except ReturnSignal:
                    pass
                break
            k = k.base
        return inst

    def _add(self, a, b):
        if isinstance(a, list) and isinstance(b, list): return a + b
        if isinstance(a, list): return a + [b]
        if isinstance(a, str) or isinstance(b, str): return gi_str(a) + gi_str(b)
        return a + b

    def eval_binop(self, node, env):
        op = node.op
        # short-circuit
        if op == '&&': return bool(self.eval_expr(node.left,env)) and bool(self.eval_expr(node.right,env))
        if op == '||': return bool(self.eval_expr(node.left,env)) or  bool(self.eval_expr(node.right,env))
        l = self.eval_expr(node.left,  env)
        r = self.eval_expr(node.right, env)
        try:
            if op == '+':  return self._add(l, r)
            if op == '-':  return l - r
            if op == '*':
                if isinstance(l, str) and isinstance(r, (int,float)): return l * int(r)
                return l * r
            if op == '/':  return l / r
            if op == '%':  return l % r
            if op == '**': return l ** r
            if op == '==': return l == r
            if op == '!=': return l != r
            if op == '<':  return l < r
            if op == '>':  return l > r
            if op == '<=': return l <= r
            if op == '>=': return l >= r
        except ZeroDivisionError:
            raise RuntimeError_("Division by zero")
        except TypeError as e:
            raise RuntimeError_(f"Type error in '{op}': {e}")

# ─────────────────────────────────────────────
#  ENTRY POINTS
# ─────────────────────────────────────────────

def run_source(src, filename='<input>'):
    try:
        tokens = Lexer(src).tokenize()
        ast    = Parser(tokens).parse()
        interp = Interpreter()
        interp.run(ast)
    except (LexError, ParseError) as e:
        print(f"\033[91m[GI Syntax Error] {e}\033[0m", file=sys.stderr)
        sys.exit(1)
    except RuntimeError_ as e:
        print(f"\033[91m[GI Runtime Error] {e}\033[0m", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)

def repl():
    BANNER = """\033[96m
  ██████╗ ██╗
 ██╔════╝ ██║
 ██║  ███╗██║
 ██║   ██║██║
 ╚██████╔╝██║
  ╚═════╝ ╚═╝   G Language Interpreted v0.1
\033[0m\033[90mType 'exit()' or Ctrl+C to quit.\033[0m\n"""
    print(BANNER)
    interp = Interpreter()
    buf = []
    depth = 0
    while True:
        try:
            prompt = "gi> " if depth == 0 else "... "
            line = input(f"\033[96m{prompt}\033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not line.strip() and depth == 0:
            continue
        buf.append(line)
        depth += line.count('{') - line.count('}')
        if depth <= 0:
            src = '\n'.join(buf)
            buf = []; depth = 0
            try:
                tokens = Lexer(src).tokenize()
                ast    = Parser(tokens).parse()
                # if single expr, print result
                if len(ast.stmts) == 1 and isinstance(ast.stmts[0], ExprStmt):
                    try:
                        val = interp.eval_expr(ast.stmts[0].expr, interp.globals)
                        if val is not None:
                            print(f"\033[93m=> {gi_str(val)}\033[0m")
                    except RuntimeError_ as e:
                        print(f"\033[91m[Error] {e}\033[0m")
                else:
                    try:
                        interp.run(ast, interp.globals)
                    except RuntimeError_ as e:
                        print(f"\033[91m[Error] {e}\033[0m")
            except (LexError, ParseError) as e:
                print(f"\033[91m[Syntax] {e}\033[0m")

def main():
    if len(sys.argv) < 2:
        repl()
    else:
        path = sys.argv[1]
        if not path.endswith('.gi'):
            print(f"Warning: expected .gi file, got '{path}'", file=sys.stderr)
        with open(path) as f:
            src = f.read()
        run_source(src, path)

if __name__ == '__main__':
    main()
