"""Portable compiled control-flow checks; not a Windows rendering/IME test."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.index('BOOLEAN ' + name + '(')
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class ColumnControls(unittest.TestCase):
    def compile_run(self, code):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('C compiler unavailable')
        with tempfile.TemporaryDirectory() as d:
            src, exe = Path(d) / 'test.c', Path(d) / 'test'
            src.write_text(code)
            subprocess.run([compiler, '-std=c11', '-Wall', '-Werror', '-Wno-unused-function',
                            str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True, capture_output=True)

    def test_header_tooltip_description_and_fallback(self):
        source = (ROOT / 'phlib/treenew.c').read_text()
        code = r'''
#include <assert.h>
#include <stddef.h>
#include <stddef.h>
#include <stdlib.h>
#include <wchar.h>
#define _In_
#define _Out_
#define FALSE 0
#define TRUE 1
#define TreeNewGetHeaderTooltip 31
#define TTM_SETMAXTIPWIDTH 0
#define TNP_TOOLTIPS_DEFAULT_MAXIMUM_WIDTH 500
#define PhMoveReference(p,s) (*(p)=(s))
typedef int BOOLEAN, LOGICAL, HFONT, HDC;
typedef unsigned long ULONG;
typedef wchar_t WCHAR;
typedef size_t SIZE_T;
typedef const wchar_t *PCWSTR;
typedef wchar_t *PPH_STRING;
typedef struct { int x, y; } POINT, *PPOINT;
typedef struct { int left, right; } RECT;
typedef struct { int cx; } SIZE;
typedef struct { int Id; PCWSTR Text; } PH_TREENEW_COLUMN, *PPH_TREENEW_COLUMN;
typedef struct { PPH_TREENEW_COLUMN Column; PCWSTR Text; } PH_TREENEW_GET_HEADER_TOOLTIP;
typedef struct {
    int TooltipColumnId, Handle, CallbackContext, Font, TextMarginPadding;
    int NewTooltipFont, TooltipUnfolding, TooltipsHandle;
    PPH_STRING TooltipText;
    int (*Callback)(int,int,PH_TREENEW_GET_HEADER_TOOLTIP *,void *,int);
} PH_TREENEW_CONTEXT, *PPH_TREENEW_CONTEXT;
static PH_TREENEW_COLUMN column = { 3, L"Private WS" };
static int width = 500, measurements;
static PCWSTR description;
static int cb(int h,int m,PH_TREENEW_GET_HEADER_TOOLTIP *p,void *x,int c) {
    assert(p->Column == &column); p->Text = description; return description != NULL;
}
static PPH_TREENEW_COLUMN PhTnpHitTestHeader(PPH_TREENEW_CONTEXT c,int f,PPOINT p,RECT *r) {
    r->left=0; r->right=width; return &column;
}
static SIZE_T PhCountStringZ(PCWSTR s) { return wcslen(s); }
static HDC GetDC(int h) { return 1; }
static HFONT SelectFont(HDC h, HFONT f) { return 0; }
static int GetTextExtentPoint32(HDC h, PCWSTR t, ULONG n, SIZE *s) { ++measurements;s->cx=100;return 1; }
static void ReleaseDC(int h,HDC d) { }
static PPH_STRING PhCreateStringEx(PCWSTR t,SIZE_T b) {
    wchar_t *s=malloc(b+sizeof(wchar_t)); wmemcpy(s,t,b/sizeof(wchar_t));s[b/sizeof(wchar_t)]=0;return s;
}
static void SendMessage(int h,int m,int w,int l) { }
'''
        code += function(source, 'PhTnpGetHeaderTooltipText')
        code += r'''
int main(void) {
    PH_TREENEW_CONTEXT c={0}; PPH_STRING text=NULL; POINT p={0}; c.Callback=cb;c.TooltipColumnId=-1;
    description=L"Resident private memory";
    assert(PhTnpGetHeaderTooltipText(&c,0,&p,&text));
    assert(wcscmp(text,description)==0 && measurements==0);free(text);
    c.TooltipColumnId=-1; description=NULL;
    assert(!PhTnpGetHeaderTooltipText(&c,0,&p,&text));
    width=10;assert(PhTnpGetHeaderTooltipText(&c,0,&p,&text));
    assert(wcscmp(text,L"Private WS")==0);free(text);
    c.TooltipColumnId=-1;description=L"";width=500;
    assert(!PhTnpGetHeaderTooltipText(&c,0,&p,&text));
    return 0;
}
'''
        self.compile_run(code)

    def test_ime_composition_message_flow(self):
        source = (ROOT / 'phlib/searchbox.c').read_text()
        ime = source[source.index('    case WM_IME_STARTCOMPOSITION:'):source.index('    case WM_CUT:')]
        chars = source[source.index('    case WM_CHAR:'):source.index('    case EM_SETCUEBANNER:')]
        self.assertIn('if (context->ImeComposing)\n                break;',
                      source[source.index('    case WM_KEYDOWN:'):source.index('    case WM_CHAR:')])
        update = function(source, 'PhSearchUpdateText')
        self.assertLess(update.index('if (Context->ImeComposing)'), update.index('searchboxTextString = PhGetWindowText'))
        code = r'''
#include <assert.h>
#include <stddef.h>
#define FALSE 0
#define TRUE 1
#define WM_IME_STARTCOMPOSITION 1
#define WM_IME_ENDCOMPOSITION 2
#define WM_IME_COMPOSITION 3
#define WM_CHAR 4
#define WM_GETDLGCODE 5
#define WM_KEYDOWN 6
#define VK_F16 127
#define VK_CONTROL 17
#define VK_ESCAPE 27
#define DLGC_WANTALLKEYS 4
#define DLGC_WANTMESSAGE 4
#define RDW_FRAME 1
#define RDW_INVALIDATE 2
typedef long LRESULT;
typedef struct { int ImeComposing, PreviousFocusWindowHandle; } CTX;
typedef struct { int message; } MSG;
static int updates, oldCalls;
static LRESULT CallWindowProc(int o,int w,int msg,int wp,long lp) { ++oldCalls;return 8; }
static void PhSearchUpdateText(int w,CTX *c,int force) { if (!c->ImeComposing) ++updates; }
static void RedrawWindow(int w,void *r,void *x,int flags) { }
static int GetAsyncKeyState(int k) { return 0; }
static int GetWindowTextLength(int w) { return 1; }
static LRESULT dispatch(CTX *context,int WindowMessage,int wParam,long lParam) {
    int WindowHandle=0,oldWndProc=0;
    switch(WindowMessage) {
'''
        code += ime + chars
        code += r'''
    }
    return CallWindowProc(oldWndProc,WindowHandle,WindowMessage,wParam,lParam);
}
int main(void) {
    CTX c={0};
    dispatch(&c,WM_IME_STARTCOMPOSITION,0,0); assert(c.ImeComposing);
    dispatch(&c,WM_IME_COMPOSITION,0,0); assert(updates==0);
    dispatch(&c,WM_CHAR,0,0); assert(updates==0);
    assert(dispatch(&c,WM_GETDLGCODE,13,0)&DLGC_WANTALLKEYS);
    dispatch(&c,WM_IME_ENDCOMPOSITION,0,0);assert(!c.ImeComposing && updates==1);
    dispatch(&c,WM_CHAR,0,0);assert(updates==2);
    dispatch(&c,WM_IME_COMPOSITION,0,0);assert(updates==3);
    dispatch(&c,WM_IME_STARTCOMPOSITION,0,0);
    dispatch(&c,WM_IME_ENDCOMPOSITION,0,0);assert(updates==4);
    return 0;
}
'''
        self.compile_run(code)

    def test_callback_enum_is_appended(self):
        header = (ROOT / 'phlib/include/treenew.h').read_text()
        self.assertLess(header.index('TreeNewReorderCancel,'), header.index('TreeNewGetHeaderTooltip,'))
        self.assertLess(header.index('TreeNewGetHeaderTooltip,'), header.index('MaxTreeNewMessage'))


if __name__ == '__main__':
    unittest.main()
