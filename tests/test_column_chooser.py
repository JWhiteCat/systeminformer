"""Execute actual chooser identity/search/move functions with a portable Win32-list shim.
Not a native GUI/IME test: controls and the established search engine are mocked.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def function(source, name):
    start = source.index(name + '(')
    start = source.rfind('\n', 0, start) + 1
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

class ColumnChooserTests(unittest.TestCase):
    def test_tooltip_resolves_current_row_not_stale_hover(self):
        source = (ROOT / 'SystemInformer/chcol.c').read_text()
        notify = source.split('case WM_NOTIFY:', 1)[1].split('case WM_COMMAND:', 1)[0]
        self.assertIn('GetCursorPos(&point)', notify)
        self.assertIn('LB_ITEMFROMPOINT', notify)
        self.assertIn('ListBox_GetItemRect(listHandle, index, &rect)', notify)
        self.assertNotIn('context->HotListIndex', notify)
        scroll = source.split('case WM_MOUSEWHEEL:', 1)[1].split('case WM_MOUSELEAVE:', 1)[0]
        self.assertIn('TTM_POP', scroll)

    def test_compiled_search_and_identity(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler unavailable')
        source = (ROOT / 'SystemInformer/chcol.c').read_text()
        header = (ROOT / 'SystemInformer/include/proctree.h').read_text()
        ids = '\n'.join(re.findall(r'^#define PHPRTLC_.*$', header, re.M))
        prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <wchar.h>
#include <wctype.h>
#include <stddef.h>
#include <string.h>
#define _In_
#define _In_opt_
#define FALSE 0
#define TRUE 1
#define ULONG_MAX ((unsigned long)-1)
#define LB_ERR -1
#define LB_ERRSPACE -2
#define PH_UI_LANGUAGE_CHINESE_SIMPLIFIED 1
#define RTL_NUMBER_OF(x) (sizeof(x)/sizeof((x)[0]))
#define WM_COMMAND 1
#define IDC_ACTIVE 1
#define LBN_SELCHANGE 1
#define MAKEWPARAM(a,b) 0
#define PH_WINDOW_CONTEXT_DEFAULT 0
#define VOID void
#define CONST const
#define FORCEINLINE inline
#define __forceinline inline
#define NTAPI
#define PH_UI_LANGUAGE_ENGLISH 0
typedef unsigned long ULONG;
typedef uintptr_t ULONG_PTR;
typedef int BOOLEAN, LONG;
typedef const wchar_t *PCWSTR;
typedef intptr_t LPARAM, LRESULT;
typedef struct { ULONG Id; PCWSTR Text; } PH_TREENEW_COLUMN, *PPH_TREENEW_COLUMN;
typedef struct { void *Items[120]; ULONG Count; } LIST, *PPH_LIST;
typedef struct { const wchar_t *Buffer; size_t Length; } PH_STRINGREF;
typedef struct { PPH_TREENEW_COLUMN Items[120]; LONG Count, Selection; } BOX, *HWND;
typedef struct {
 BOOLEAN ProcessColumns;
 HWND ActiveWindowHandle, InactiveWindowHandle;
 PPH_LIST ActiveListArray, InactiveListArray;
 ULONG_PTR ActiveMatchHandle, InactiveMatchHandle;
} COLUMNS_DIALOG_CONTEXT, *PCOLUMNS_DIALOG_CONTEXT;
static ULONG language;
static ULONG PhGetUiLanguage(void) { return language; }
static LRESULT ListBox_GetItemData(HWND w, LONG i) { return i < 0 || i >= w->Count ? LB_ERR : (LRESULT)w->Items[i]; }
static LONG ListBox_InsertString(HWND w, LONG i, PCWSTR s) {
 if (i < 0 || i > w->Count) i=w->Count;
 memmove(w->Items+i+1,w->Items+i,(w->Count-i)*sizeof(void*)); w->Count++; return i;
}
static void ListBox_SetItemData(HWND w,LONG i,LPARAM p) { w->Items[i]=(void*)p; }
static LONG ListBox_GetCount(HWND w) {return w->Count;}
static void ListBox_SetCurSel(HWND w,LONG i) {w->Selection=i;}
static HWND GetParent(HWND w) {return w;}
static void SendMessage(HWND w,int m,int a,LPARAM b) {}
static void PhInitializeStringRef(PH_STRINGREF *r,PCWSTR s) {r->Buffer=s;r->Length=wcslen(s)*sizeof(wchar_t);}
static BOOLEAN PhSearchControlMatch(ULONG_PTR handle,PH_STRINGREF *r) {
 PCWSTR q=(PCWSTR)handle;
 for(PCWSTR p=r->Buffer; *p; p++) {
  size_t j=0; while(q[j] && p[j] && towlower(p[j])==towlower(q[j])) j++;
  if(!q[j]) return TRUE;
 }
 return FALSE;
}
static void PhRemoveItemsList(PPH_LIST l,ULONG i,ULONG n) {memmove(l->Items+i,l->Items+i+n,(l->Count-i-n)*sizeof(void*));l->Count-=n;}
static void PhInsertItemList(PPH_LIST l,ULONG i,void *p) {memmove(l->Items+i+1,l->Items+i,(l->Count-i)*sizeof(void*)); l->Items[i]=p;l->Count++;}
static void PhAddItemList(PPH_LIST l,void *p) {l->Items[l->Count++]=p;}
'''
        names = ['PhpColumnsGetItem','PhpColumnsIndexOf','PhpColumnsInsertItem','PhpColumnsMatch']
        body = '\n'.join(function(source, n) for n in names)
        refresh = r'''
#define WM_SETREDRAW 2
#define min(a,b) ((a)<(b)?(a):(b))
typedef int (*_CoreCrtSecureSearchSortCompareFunction)(void*,const void*,const void*);
static PCOLUMNS_DIALOG_CONTEXT currentContext;
static PCOLUMNS_DIALOG_CONTEXT PhGetWindowContext(HWND w,int k) {return currentContext;}
static LONG ListBox_GetCurSel(HWND w) {return w->Selection;}
static void ListBox_ResetContent(HWND w) {w->Count=0;w->Selection=-1;}
static void InvalidateRect(HWND w,void*p,int erase) {}
static int GetDlgCtrlID(HWND w) {return 1;}
static void qsort_s(void*a,size_t n,size_t size,_CoreCrtSecureSearchSortCompareFunction cmp,void*c) {}
static int PhpInactiveColumnsCompareNameTn(void*c,const void*a,const void*b) {return 0;}
static void PhpColumnsSetHotItem(PCOLUMNS_DIALOG_CONTEXT c,HWND w,LONG i) {}
'''
        body += refresh + '\n'.join(function(source,n) for n in ['PhpColumnsResetListBox','PhpColumnsRefreshLists','PhpColumnsMoveActiveItem','PhpColumnsShowItem','PhpColumnsHideItem'])
        main = r'''
int main(void) {
 BOX active={0},inactive={0}; LIST a={0},b={0};
 COLUMNS_DIALOG_CONTEXT c={TRUE,&active,&inactive,&a,&b,0,0};
 currentContext=&c; active.Selection=inactive.Selection=-1;
 PH_TREENEW_COLUMN ws={PHPRTLC_PRIVATEWS,L"私有工作集"},pb={PHPRTLC_PRIVATEBYTES,L"私有字节"},unknown={900,L"Plugin"};
 assert(PhpColumnsMatch(&c,0,&ws));
 assert(PhpColumnsMatch(&c,(ULONG_PTR)L"Private WS",&ws));
 assert(PhpColumnsMatch(&c,(ULONG_PTR)L"private ws",&ws));
 assert(PhpColumnsMatch(&c,(ULONG_PTR)L"私有",&ws));
 assert(!PhpColumnsMatch(&c,(ULONG_PTR)L"not-a-column",&ws));
 ws.Text=L"Private WS"; assert(PhpColumnsMatch(&c,(ULONG_PTR)L"私有",&ws));
 c.ProcessColumns=FALSE; assert(!PhpColumnsMatch(&c,(ULONG_PTR)L"私有",&ws)); c.ProcessColumns=TRUE;
 assert(PhpColumnsMatch(&c,(ULONG_PTR)L"Plugin",&unknown));
 assert(!PhpColumnsMatch(&c,(ULONG_PTR)L"Private WS",&unknown));
 // Identical localized captions must never merge distinct column identities.
 ws.Text=pb.Text=L"same"; PhAddItemList(&a,&ws); PhAddItemList(&a,&pb);
 PhpColumnsRefreshLists(&c); active.Selection=1; PhpColumnsHideItem(&c,1);
 assert(active.Selection==0);
 assert(a.Count==1 && a.Items[0]==&ws && b.Items[0]==&pb);
 PhpColumnsShowItem(&c,0,0); assert(a.Items[0]==&pb && a.Items[1]==&ws);
 PhpColumnsMoveActiveItem(&c,0,2); assert(a.Items[0]==&ws && a.Items[1]==&pb);
 c.ActiveMatchHandle=(ULONG_PTR)L"Private WS"; c.InactiveMatchHandle=(ULONG_PTR)L"no-match";
 PhpColumnsRefreshLists(&c); assert(active.Count==1 && inactive.Count==0);
 PhpColumnsHideItem(&c,0); assert(active.Count==0 && inactive.Count==0 && a.Items[0]==&pb);
 c.InactiveMatchHandle=0; PhpColumnsRefreshLists(&c); assert(inactive.Count==1);
 PhpColumnsShowItem(&c,0,-1); assert(active.Count==1 && a.Count==2);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            c = Path(d)/'chooser.c'; binary=Path(d)/'chooser'
            c.write_text(prelude+ids+'\n#include "proccolmeta.h"\n'+body+main)
            subprocess.run([cc,'-std=c11','-I',str(ROOT/'SystemInformer/include'),str(c),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__ == '__main__': unittest.main()
