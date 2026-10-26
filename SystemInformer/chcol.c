/*
 * Copyright (c) 2022 Winsider Seminars & Solutions, Inc.  All rights reserved.
 *
 * This file is part of System Informer.
 *
 * Authors:
 *
 *     wj32    2010
 *     dmex    2017-2026
 *
 */

#include <phapp.h>
#include <settings.h>
#include <proctree.h>
#include <proccolmeta.h>

typedef struct _COLUMNS_DIALOG_CONTEXT
{
    HWND ControlHandle;
    BOOLEAN ProcessColumns;
    HWND TooltipHandle;
    ULONG_PTR InactiveMatchHandle;
    ULONG_PTR ActiveMatchHandle;
    HFONT ControlFont;
    ULONG Type;
    PPH_LIST Columns;

    HBRUSH BrushNormal;
    HBRUSH BrushPushed;
    HBRUSH BrushHot;
    HBRUSH BrushHover;
    COLORREF TextColor;

    WNDPROC InactiveListWindowProc;
    WNDPROC ActiveListWindowProc;
    HWND HotListHandle;
    LONG HotListIndex;
    BOOLEAN MouseTracking;

    HWND InactiveWindowHandle;
    HWND ActiveWindowHandle;
    HWND SearchInactiveHandle;
    HWND SearchActiveHandle;
    HWND HideWindowHandle;
    HWND ShowWindowHandle;
    HWND MoveUpHandle;
    HWND MoveDownHandle;
    PPH_LIST InactiveListArray;
    PPH_LIST ActiveListArray;

    UINT DragListMessage;
    HWND DragSourceHandle;
    LONG DragItemIndex;
    HIMAGELIST DragImageList;
    POINT DragImageHotspot;
    LONG DragImageWidth;
    LONG DragImageHeight;
    HWND DragInsertHandle;
    LONG DragInsertIndex;
} COLUMNS_DIALOG_CONTEXT, *PCOLUMNS_DIALOG_CONTEXT;

INT_PTR CALLBACK PhpColumnsDlgProc(
    _In_ HWND hwndDlg,
    _In_ UINT uMsg,
    _In_ WPARAM wParam,
    _In_ LPARAM lParam
    );

/**
 * Shows the column chooser dialog for a control.
 *
 * \param ParentWindowHandle Parent window for the dialog.
 * \param ControlHandle The handle to the control.
 * \param Type The type of the control.
 */
VOID PhShowChooseColumnsDialog(
    _In_ HWND ParentWindowHandle,
    _In_ HWND ControlHandle,
    _In_ ULONG Type
    )
{
    COLUMNS_DIALOG_CONTEXT context;

    memset(&context, 0, sizeof(COLUMNS_DIALOG_CONTEXT));
    context.ControlHandle = ControlHandle;
    context.ProcessColumns = PhIsProcessTreeList(ControlHandle);
    context.Type = Type;

    if (Type == PH_CONTROL_TYPE_TREE_NEW)
        context.Columns = PhCreateList(TreeNew_GetColumnCount(ControlHandle));
    else
        return;

    PhDialogBox(
        PhInstanceHandle,
        MAKEINTRESOURCE(IDD_CHOOSECOLUMNS),
        ParentWindowHandle,
        PhpColumnsDlgProc,
        &context
        );

    PhDereferenceObject(context.Columns);
}

/**
 * Compares the display index of two columns for sorting.
 *
 * \param Context Optional callback context.
 * \param elem1 First column pointer.
 * \param elem2 Second column pointer.
 * \return Comparison result.
 */
static int __cdecl PhpColumnsCompareDisplayIndexTn(
    _In_ void* Context,
    _In_ void const* elem1,
    _In_ void const* elem2
    )
{
    PPH_TREENEW_COLUMN column1 = *(PPH_TREENEW_COLUMN *)elem1;
    PPH_TREENEW_COLUMN column2 = *(PPH_TREENEW_COLUMN *)elem2;

    return uintcmp(column1->DisplayIndex, column2->DisplayIndex);
}

/**
 * Compares the names of two inactive columns alphabetically.
 *
 * \param Context Optional callback context.
 * \param elem1 First string pointer.
 * \param elem2 Second string pointer.
 * \return Comparison result.
 */
static int __cdecl PhpInactiveColumnsCompareNameTn(
    _In_ void* Context,
    _In_ const void *elem1,
    _In_ const void *elem2
    )
{
    PPH_TREENEW_COLUMN column1 = *(PPH_TREENEW_COLUMN *)elem1;
    PPH_TREENEW_COLUMN column2 = *(PPH_TREENEW_COLUMN *)elem2;

    return PhCompareStringZ(column1->Text, column2->Text, FALSE);
}

// List-box item data carries identity; captions are not unique (especially after translation).
static PPH_TREENEW_COLUMN PhpColumnsGetItem(HWND ListBoxHandle, LONG Index)
{
    LRESULT item = ListBox_GetItemData(ListBoxHandle, Index);
    return item == LB_ERR ? NULL : (PPH_TREENEW_COLUMN)item;
}

static ULONG PhpColumnsIndexOf(PPH_LIST List, PPH_TREENEW_COLUMN Column)
{
    for (ULONG i = 0; i < List->Count; i++)
        if (List->Items[i] == Column)
            return i;
    return ULONG_MAX;
}

static LONG PhpColumnsInsertItem(HWND ListBoxHandle, LONG Index, PPH_TREENEW_COLUMN Column)
{
    LONG index = ListBox_InsertString(ListBoxHandle, Index, Column->Text);
    if (index != LB_ERR && index != LB_ERRSPACE)
        ListBox_SetItemData(ListBoxHandle, index, (LPARAM)Column);
    return index;
}

static BOOLEAN PhpColumnsMatch(PCOLUMNS_DIALOG_CONTEXT Context, ULONG_PTR MatchHandle, PPH_TREENEW_COLUMN Column)
{
    PH_STRINGREF text;
    const PH_PROCESS_COLUMN_METADATA *metadata;
    PCWSTR names[4];

    if (!MatchHandle)
        return TRUE;

    names[0] = Column->Text;
    metadata = Context->ProcessColumns ? PhpGetProcessColumnMetadata(Column->Id) : NULL;
    names[1] = metadata ? metadata->EnglishName : NULL;
    names[2] = metadata ? metadata->ChineseName : NULL;
    names[3] = metadata ? metadata->Aliases : NULL;

    for (ULONG i = 0; i < RTL_NUMBER_OF(names); i++)
    {
        if (!names[i] || !names[i][0])
            continue;
        PhInitializeStringRef(&text, names[i]);
        if (PhSearchControlMatch(MatchHandle, &text))
            return TRUE;
    }
    return FALSE;
}

/**
 * Updates the hot (mouse-over) item, invalidating the previous and new items.
 *
 * \param Context The columns dialog context.
 * \param ListBoxHandle The list box under the mouse, or NULL for none.
 * \param ItemIndex The hot item index, or LB_ERR for none.
 */
static VOID PhpColumnsSetHotItem(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_opt_ HWND ListBoxHandle,
    _In_ LONG ItemIndex
    )
{
    RECT itemRect;

    if (Context->HotListHandle == ListBoxHandle && Context->HotListIndex == ItemIndex)
        return;

    if (Context->HotListHandle && Context->HotListIndex != LB_ERR)
    {
        if (ListBox_GetItemRect(Context->HotListHandle, Context->HotListIndex, &itemRect) != LB_ERR)
            InvalidateRect(Context->HotListHandle, &itemRect, FALSE);
    }

    Context->HotListHandle = ListBoxHandle;
    Context->HotListIndex = ItemIndex;
    if (Context->TooltipHandle)
        SendMessage(Context->TooltipHandle, TTM_UPDATE, 0, 0);

    if (ListBoxHandle && ItemIndex != LB_ERR)
    {
        if (ListBox_GetItemRect(ListBoxHandle, ItemIndex, &itemRect) != LB_ERR)
            InvalidateRect(ListBoxHandle, &itemRect, FALSE);
    }
}

/**
 * Gets the drag insert rectangle for a list box item.
 *
 * \param ListBoxHandle The handle to the list box.
 * \param ItemIndex The index of the item.
 * \param ItemRect A pointer to a RECT structure that receives the coordinates.
 * \return TRUE if successful, FALSE otherwise.
 */
static BOOLEAN PhpColumnsGetDragInsertRect(
    _In_ HWND ListBoxHandle,
    _In_ LONG ItemIndex,
    _Out_ PRECT ItemRect
    )
{
    LONG count;

    if (!ListBoxHandle || !IsWindow(ListBoxHandle))
        return FALSE;

    count = ListBox_GetCount(ListBoxHandle);

    if (count <= 0 || ItemIndex < 0)
        return FALSE;

    if (ItemIndex >= count)
        ItemIndex = count - 1;

    return ListBox_GetItemRect(ListBoxHandle, ItemIndex, ItemRect) != LB_ERR;
}

/**
 * Sets the drag insert position and updates the display.
 *
 * \param Context The columns dialog context.
 * \param ListBoxHandle The handle to the list box, or NULL to clear the insert position.
 * \param ItemIndex The index of the item.
 */
static VOID PhpColumnsSetDragInsert(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_opt_ HWND ListBoxHandle,
    _In_ LONG ItemIndex
    )
{
    RECT itemRect;
    HWND oldListBoxHandle;
    BOOLEAN dragImageActive;

    // Only hide the drag image when the insert position changes. (Hiding and showing it on every DL_DRAGGING causes flicker.)
    if (Context->DragInsertHandle == ListBoxHandle && Context->DragInsertIndex == ItemIndex)
        return;

    dragImageActive = !!Context->DragImageList;
    oldListBoxHandle = Context->DragInsertHandle;

    if (dragImageActive)
        PhImageListDragShowNolock(FALSE);

    if (PhpColumnsGetDragInsertRect(Context->DragInsertHandle, Context->DragInsertIndex, &itemRect))
        InvalidateRect(Context->DragInsertHandle, &itemRect, FALSE);

    Context->DragInsertHandle = ListBoxHandle;
    Context->DragInsertIndex = ItemIndex;

    if (PhpColumnsGetDragInsertRect(Context->DragInsertHandle, Context->DragInsertIndex, &itemRect))
        InvalidateRect(Context->DragInsertHandle, &itemRect, FALSE);

    if (oldListBoxHandle)
        UpdateWindow(oldListBoxHandle);

    if (Context->DragInsertHandle && Context->DragInsertHandle != oldListBoxHandle)
        UpdateWindow(Context->DragInsertHandle);

    if (dragImageActive)
        PhImageListDragShowNolock(TRUE);
}

/**
 * Creates a drag image for a list box item.
 *
 * \param ListBoxHandle The handle to the list box.
 * \param ItemIndex The index of the item.
 * \param CursorPosition The cursor position.
 * \param Hotspot A pointer to a POINT structure that receives the hotspot coordinates.
 * \param ImageWidth A pointer to a LONG that receives the image width.
 * \param ImageHeight A pointer to a LONG that receives the image height.
 * \return The handle to the created image list, or NULL on failure.
 */
static HIMAGELIST PhpColumnsCreateDragImage(
    _In_ HWND ListBoxHandle,
    _In_ LONG ItemIndex,
    _In_ POINT CursorPosition,
    _Out_ PPOINT Hotspot,
    _Out_ PLONG ImageWidth,
    _Out_ PLONG ImageHeight
    )
{
    RECT itemRect;
    POINT clientPoint;
    LONG width;
    LONG height;
    HDC windowDc;
    HDC bufferDc;
    HBITMAP bitmap;
    HBITMAP oldBitmap;
    HIMAGELIST imageList;

    Hotspot->x = 0;
    Hotspot->y = 0;
    *ImageWidth = 0;
    *ImageHeight = 0;

    if (!ListBoxHandle || ItemIndex < 0 ||
        ListBox_GetItemRect(ListBoxHandle, ItemIndex, &itemRect) == LB_ERR)
    {
        return NULL;
    }

    width = itemRect.right - itemRect.left;
    height = itemRect.bottom - itemRect.top;

    if (width <= 0 || height <= 0)
        return NULL;

    *ImageWidth = width;
    *ImageHeight = height;

    clientPoint = CursorPosition;

    if (!ScreenToClient(ListBoxHandle, &clientPoint))
        return NULL;

    Hotspot->x = clientPoint.x - itemRect.left;
    Hotspot->y = clientPoint.y - itemRect.top;

    windowDc = GetDC(ListBoxHandle);

    if (!windowDc)
        return NULL;

    bufferDc = CreateCompatibleDC(windowDc);
    bitmap = PhCreateDIBSection(windowDc, PHBF_TOPDOWNDIB, width, height, NULL);

    if (!bufferDc || !bitmap)
    {
        if (bitmap)
            DeleteBitmap(bitmap);
        if (bufferDc)
            DeleteDC(bufferDc);

        ReleaseDC(ListBoxHandle, windowDc);
        return NULL;
    }

    oldBitmap = SelectBitmap(bufferDc, bitmap);

    BitBlt(
        bufferDc,
        0,
        0,
        width,
        height,
        windowDc,
        itemRect.left,
        itemRect.top,
        SRCCOPY
        );

    SelectBitmap(bufferDc, oldBitmap);
    DeleteDC(bufferDc);
    ReleaseDC(ListBoxHandle, windowDc);

    imageList = PhImageListCreate(width, height, ILC_COLOR32, 1, 0);

    if (!imageList || PhImageListAddBitmap(imageList, bitmap, NULL) == INT_ERROR)
    {
        if (imageList)
            PhImageListDestroy(imageList);

        DeleteBitmap(bitmap);
        return NULL;
    }

    DeleteBitmap(bitmap);

    return imageList;
}

/**
 * Converts a screen point to a window point.
 *
 * \param WindowHandle The handle to the window.
 * \param ScreenPoint The screen point to convert.
 * \param WindowPoint A pointer to a POINT structure that receives the converted coordinates.
 * \return TRUE if successful, FALSE otherwise.
 */
static BOOLEAN PhpColumnsGetDragWindowPoint(
    _In_ HWND WindowHandle,
    _In_ POINT ScreenPoint,
    _Out_ PPOINT WindowPoint
    )
{
    RECT windowRect;

    if (!GetWindowRect(WindowHandle, &windowRect))
        return FALSE;

    WindowPoint->x = ScreenPoint.x - windowRect.left;
    WindowPoint->y = ScreenPoint.y - windowRect.top;

    return TRUE;
}

/**
 * Constrains a drag window point to the bounds of a window.
 *
 * \param WindowHandle The handle to the window.
 * \param ImageWidth The width of the drag image.
 * \param ImageHeight The height of the drag image.
 * \param Hotspot The hotspot coordinates.
 * \param WindowPoint A pointer to a POINT structure that receives the constrained coordinates.
 */
static VOID PhpColumnsConstrainDragWindowPoint(
    _In_ HWND WindowHandle,
    _In_ LONG ImageWidth,
    _In_ LONG ImageHeight,
    _In_ POINT Hotspot,
    _Inout_ PPOINT WindowPoint
    )
{
    RECT windowRect;
    RECT clientRect;
    POINT clientOrigin = { 0, 0 };
    LONG minimumX;
    LONG maximumX;
    LONG minimumY;
    LONG maximumY;
    LONG clientWidth;
    LONG clientHeight;

    if (!GetWindowRect(WindowHandle, &windowRect) ||
        !GetClientRect(WindowHandle, &clientRect) ||
        !ClientToScreen(WindowHandle, &clientOrigin))
    {
        return;
    }

    clientWidth = clientRect.right - clientRect.left;
    clientHeight = clientRect.bottom - clientRect.top;
    clientRect.left = clientOrigin.x - windowRect.left;
    clientRect.right = clientRect.left + clientWidth;
    clientRect.top = clientOrigin.y - windowRect.top;
    clientRect.bottom = clientRect.top + clientHeight;

    minimumX = clientRect.left + Hotspot.x;
    maximumX = clientRect.right - ImageWidth + Hotspot.x;
    minimumY = clientRect.top + Hotspot.y;
    maximumY = clientRect.bottom - ImageHeight + Hotspot.y;

    if (maximumX < minimumX)
        WindowPoint->x = minimumX;
    else if (WindowPoint->x < minimumX)
        WindowPoint->x = minimumX;
    else if (WindowPoint->x > maximumX)
        WindowPoint->x = maximumX;

    if (maximumY < minimumY)
        WindowPoint->y = minimumY;
    else if (WindowPoint->y < minimumY)
        WindowPoint->y = minimumY;
    else if (WindowPoint->y > maximumY)
        WindowPoint->y = maximumY;
}

/**
 * Destroys the drag image list and ends the drag operation.
 *
 * \param Context The columns dialog context.
 * \param LockWindowHandle The handle to the lock window.
 */
static VOID PhpColumnsDestroyDragImage(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_ HWND LockWindowHandle
    )
{
    HIMAGELIST imageList;

    if (!(imageList = Context->DragImageList))
        return;

    Context->DragImageList = NULL;
    Context->DragImageHotspot.x = 0;
    Context->DragImageHotspot.y = 0;
    Context->DragImageWidth = 0;
    Context->DragImageHeight = 0;

    PhImageListDragLeave(LockWindowHandle);
    PhImageListEndDrag();
    PhImageListDestroy(imageList);
}

/**
 * Draws the drag insert indicator.
 *
 * \param Context The columns dialog context.
 * \param DrawInfo A pointer to a DRAWITEMSTRUCT structure containing drawing information.
 */
static VOID PhpColumnsDrawDragInsert(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_ LPDRAWITEMSTRUCT DrawInfo
    )
{
    LONG count;
    LONG lineThickness;
    RECT lineRect;
    COLORREF oldColor;

    if (DrawInfo->hwndItem != Context->DragInsertHandle || Context->DragInsertIndex < 0)
        return;

    count = ListBox_GetCount(DrawInfo->hwndItem);

    if (count <= 0)
        return;

    if (Context->DragInsertIndex < count)
    {
        if ((LONG)DrawInfo->itemID != Context->DragInsertIndex)
            return;

        lineThickness = PhScaleToDisplay(2, PhGetWindowDpi(DrawInfo->hwndItem));
        lineRect = DrawInfo->rcItem;
        lineRect.bottom = lineRect.top + lineThickness;
    }
    else
    {
        if ((LONG)DrawInfo->itemID != count - 1)
            return;

        lineThickness = PhScaleToDisplay(2, PhGetWindowDpi(DrawInfo->hwndItem));
        lineRect = DrawInfo->rcItem;
        lineRect.top = lineRect.bottom - lineThickness;
    }

    oldColor = SetDCBrushColor(
        DrawInfo->hDC,
        PhEnableThemeSupport ? PhThemeWindowHighlightColor : GetSysColor(COLOR_HIGHLIGHT)
        );
    FillRect(DrawInfo->hDC, &lineRect, PhGetStockBrush(DC_BRUSH));
    SetDCBrushColor(DrawInfo->hDC, oldColor);
}

/**
 * Resets a list box and populates it with items, optionally sorting and filtering them.
 *
 * \param ListBoxHandle The handle to the list box control.
 * \param MatchHandle The search control match handle for filtering.
 * \param Array The list containing the items to display.
 * \param CompareFunction Optional comparison function for sorting.
 */
VOID PhpColumnsResetListBox(
    _In_ HWND ListBoxHandle,
    _In_ ULONG_PTR MatchHandle,
    _In_ PPH_LIST Array,
    _In_opt_ _CoreCrtSecureSearchSortCompareFunction CompareFunction
    )
{
    PCOLUMNS_DIALOG_CONTEXT context = PhGetWindowContext(ListBoxHandle, PH_WINDOW_CONTEXT_DEFAULT);
    LONG oldSelection = ListBox_GetCurSel(ListBoxHandle);
    PPH_TREENEW_COLUMN selectedColumn = PhpColumnsGetItem(ListBoxHandle, oldSelection);
    LONG newSelection = LB_ERR;
    SendMessage(ListBoxHandle, WM_SETREDRAW, FALSE, 0);
    ListBox_ResetContent(ListBoxHandle);
    if (CompareFunction)
        qsort_s(Array->Items, Array->Count, sizeof(ULONG_PTR), CompareFunction, NULL);
    for (ULONG i = 0; i < Array->Count; i++)
    {
        PPH_TREENEW_COLUMN column = Array->Items[i];
        if (PhpColumnsMatch(context, MatchHandle, column))
        {
            LONG index = PhpColumnsInsertItem(ListBoxHandle, -1, column);
            if (column == selectedColumn)
                newSelection = index;
        }
    }
    if (newSelection == LB_ERR && oldSelection != LB_ERR && ListBox_GetCount(ListBoxHandle) > 0)
        newSelection = min(oldSelection, ListBox_GetCount(ListBoxHandle) - 1);
    ListBox_SetCurSel(ListBoxHandle, newSelection);
    SendMessage(ListBoxHandle, WM_SETREDRAW, TRUE, 0);
    InvalidateRect(ListBoxHandle, NULL, TRUE);
    SendMessage(GetParent(ListBoxHandle), WM_COMMAND,
        MAKEWPARAM(GetDlgCtrlID(ListBoxHandle), LBN_SELCHANGE), (LPARAM)ListBoxHandle);
}

static VOID PhpColumnsRefreshLists(PCOLUMNS_DIALOG_CONTEXT Context)
{
    PhpColumnsSetHotItem(Context, NULL, LB_ERR);
    PhpColumnsResetListBox(Context->InactiveWindowHandle, Context->InactiveMatchHandle,
        Context->InactiveListArray, PhpInactiveColumnsCompareNameTn);
    PhpColumnsResetListBox(Context->ActiveWindowHandle, Context->ActiveMatchHandle,
        Context->ActiveListArray, NULL);
}

// Moves the item at listbox row FromIndex to insert position ToIndex (the item is
// inserted before the item currently at ToIndex; ToIndex == count appends).
/**
 * Moves an item in the active columns list from one position to another.
 *
 * \param Context The columns dialog context.
 * \param FromIndex The index of the item to move.
 * \param ToIndex The destination index.
 */
static VOID PhpColumnsMoveActiveItem(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_ LONG FromIndex,
    _In_ LONG ToIndex
    )
{
    PPH_TREENEW_COLUMN item = PhpColumnsGetItem(Context->ActiveWindowHandle, FromIndex);
    PPH_TREENEW_COLUMN target = PhpColumnsGetItem(Context->ActiveWindowHandle, ToIndex);
    ULONG from = PhpColumnsIndexOf(Context->ActiveListArray, item);
    ULONG to = target ? PhpColumnsIndexOf(Context->ActiveListArray, target) : Context->ActiveListArray->Count;

    if (!item || from == ULONG_MAX || ToIndex < 0 || to == ULONG_MAX)
        return;
    if (from == to || from + 1 == to)
        return;
    PhRemoveItemsList(Context->ActiveListArray, from, 1);
    if (to > from)
        to--;
    PhInsertItemList(Context->ActiveListArray, to, item);
    PhpColumnsRefreshLists(Context);
    // Restore selection by identity after filtering (not by translated text).
    for (LONG i = 0; i < ListBox_GetCount(Context->ActiveWindowHandle); i++)
        if (PhpColumnsGetItem(Context->ActiveWindowHandle, i) == item)
        {
            ListBox_SetCurSel(Context->ActiveWindowHandle, i);
            SendMessage(GetParent(Context->ActiveWindowHandle), WM_COMMAND,
                MAKEWPARAM(IDC_ACTIVE, LBN_SELCHANGE), (LPARAM)Context->ActiveWindowHandle);
            break;
        }
}

static VOID PhpColumnsShowItem(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_ LONG InactiveIndex,
    _In_ LONG ActiveInsertIndex
    )
{
    PPH_TREENEW_COLUMN item = PhpColumnsGetItem(Context->InactiveWindowHandle, InactiveIndex);
    PPH_TREENEW_COLUMN target = PhpColumnsGetItem(Context->ActiveWindowHandle, ActiveInsertIndex);
    ULONG from = PhpColumnsIndexOf(Context->InactiveListArray, item);
    ULONG to = target ? PhpColumnsIndexOf(Context->ActiveListArray, target) : Context->ActiveListArray->Count;

    if (!item || from == ULONG_MAX || to == ULONG_MAX)
        return;
    PhRemoveItemsList(Context->InactiveListArray, from, 1);
    PhInsertItemList(Context->ActiveListArray, to, item);
    PhpColumnsRefreshLists(Context);
}

static VOID PhpColumnsHideItem(
    _In_ PCOLUMNS_DIALOG_CONTEXT Context,
    _In_ LONG ActiveIndex
    )
{
    PPH_TREENEW_COLUMN item = PhpColumnsGetItem(Context->ActiveWindowHandle, ActiveIndex);
    ULONG from = PhpColumnsIndexOf(Context->ActiveListArray, item);

    if (!item || from == ULONG_MAX)
        return;
    PhRemoveItemsList(Context->ActiveListArray, from, 1);
    PhAddItemList(Context->InactiveListArray, item);
    PhpColumnsRefreshLists(Context);
}

// Returns the insert row under the cursor for a drag list target, count when the
// cursor is inside the listbox but below the last item, or INT_ERROR when outside.
/**
 * Finds the drag insert index under the cursor for a list box.
 *
 * \param ListBoxHandle The handle to the list box.
 * \param Point The current cursor coordinates.
 * \param AutoScroll Whether to auto-scroll the list box.
 * \return The insert index, or INT_ERROR if the cursor is outside.
 */
static LONG PhpColumnsDragTargetIndex(
    _In_ HWND ListBoxHandle,
    _In_ POINT Point,
    _In_ BOOLEAN AutoScroll
    )
{
    LONG index;
    RECT rect;

    index = LBItemFromPt(ListBoxHandle, Point, AutoScroll);

    if (index == INT_ERROR)
    {
        GetWindowRect(ListBoxHandle, &rect);

        if (PtInRect(&rect, Point))
            index = ListBox_GetCount(ListBoxHandle);
    }

    return index;
}

/**
 * Callback for the inactive columns search control.
 *
 * \param MatchHandle The search control match handle.
 * \param Context The columns dialog context.
 */
_Function_class_(PH_SEARCHCONTROL_CALLBACK)
VOID NTAPI PhpInactiveColumnsSearchControlCallback(
    _In_ ULONG_PTR MatchHandle,
    _In_opt_ PVOID Context
    )
{
    PCOLUMNS_DIALOG_CONTEXT context = Context;

    PhpColumnsSetHotItem(context, NULL, LB_ERR);

    context->InactiveMatchHandle = MatchHandle;
    PhpColumnsResetListBox(
        context->InactiveWindowHandle,
        MatchHandle,
        context->InactiveListArray,
        PhpInactiveColumnsCompareNameTn
        );
}

/**
 * Callback for the active columns search control.
 *
 * \param MatchHandle The search control match handle.
 * \param Context The columns dialog context.
 */
_Function_class_(PH_SEARCHCONTROL_CALLBACK)
VOID NTAPI PhpActiveColumnsSearchControlCallback(
    _In_ ULONG_PTR MatchHandle,
    _In_opt_ PVOID Context
    )
{
    PCOLUMNS_DIALOG_CONTEXT context = Context;

    PhpColumnsSetHotItem(context, NULL, LB_ERR);

    context->ActiveMatchHandle = MatchHandle;
    PhpColumnsResetListBox(
        context->ActiveWindowHandle,
        MatchHandle,
        context->ActiveListArray,
        NULL
        );
}

/**
 * Window procedure for the column list boxes providing hot (mouse-over) tracking.
 *
 * \param WindowHandle The handle to the list box window.
 * \param WindowMessage The window message.
 * \param wParam Additional message-specific information.
 * \param lParam Additional message-specific information.
 * \return LRESULT The message result.
 */
static LRESULT CALLBACK PhpColumnsListBoxWndProc(
    _In_ HWND WindowHandle,
    _In_ UINT WindowMessage,
    _In_ WPARAM wParam,
    _In_ LPARAM lParam
    )
{
    PCOLUMNS_DIALOG_CONTEXT context;
    WNDPROC oldWndProc;

    if (!(context = PhGetWindowContext(WindowHandle, PH_WINDOW_CONTEXT_DEFAULT)))
        return DefWindowProc(WindowHandle, WindowMessage, wParam, lParam);

    if (WindowHandle == context->ActiveWindowHandle)
        oldWndProc = context->ActiveListWindowProc;
    else
        oldWndProc = context->InactiveListWindowProc;

    switch (WindowMessage)
    {
    case WM_NCDESTROY:
        {
            SetWindowLongPtr(WindowHandle, GWLP_WNDPROC, (LONG_PTR)oldWndProc);
            PhRemoveWindowContext(WindowHandle, PH_WINDOW_CONTEXT_DEFAULT);
        }
        break;
    case WM_MOUSEMOVE:
        {
            LRESULT result;
            LONG index;

            // Repainting items while the drag image is shown leaves artifacts. (The drag list captures the mouse.)
            if (context->DragItemIndex != LB_ERR)
                break;

            result = SendMessage(WindowHandle, LB_ITEMFROMPOINT, 0, lParam);
            index = HIWORD(result) == 0 ? (LONG)(SHORT)LOWORD(result) : LB_ERR;

            PhpColumnsSetHotItem(context, WindowHandle, index);

            if (!context->MouseTracking)
            {
                TRACKMOUSEEVENT trackMouseEvent = { sizeof(TRACKMOUSEEVENT), TME_LEAVE, WindowHandle, 0 };

                context->MouseTracking = !!TrackMouseEvent(&trackMouseEvent);
            }
        }
        break;
    case WM_MOUSEWHEEL:
    case WM_VSCROLL:
    case WM_KEYDOWN:
        // Scrolling can change the row under a stationary cursor.
        if (context->TooltipHandle)
            SendMessage(context->TooltipHandle, TTM_POP, 0, 0);
        PhpColumnsSetHotItem(context, NULL, LB_ERR);
        break;
    case WM_MOUSELEAVE:
        {
            context->MouseTracking = FALSE;
            PhpColumnsSetHotItem(context, NULL, LB_ERR);
        }
        break;
    }

    return CallWindowProc(oldWndProc, WindowHandle, WindowMessage, wParam, lParam);
}

/**
 * The dialog procedure for the column chooser dialog.
 *
 * \param hwndDlg The handle to the dialog window.
 * \param uMsg The window message.
 * \param wParam Additional message-specific information.
 * \param lParam Additional message-specific information.
 * \return INT_PTR Dialog return value.
 */
INT_PTR CALLBACK PhpColumnsDlgProc(
    _In_ HWND hwndDlg,
    _In_ UINT uMsg,
    _In_ WPARAM wParam,
    _In_ LPARAM lParam
    )
{
    PCOLUMNS_DIALOG_CONTEXT context = NULL;

    if (uMsg == WM_INITDIALOG)
    {
        context = (PCOLUMNS_DIALOG_CONTEXT)lParam;
        PhSetWindowContext(hwndDlg, PH_WINDOW_CONTEXT_DEFAULT, context);
    }
    else
    {
        context = PhGetWindowContext(hwndDlg, PH_WINDOW_CONTEXT_DEFAULT);
    }

    if (!context)
        return FALSE;

    switch (uMsg)
    {
    case WM_INITDIALOG:
        {
            ULONG count;
            ULONG total;
            ULONG i;
            PPH_LIST displayOrderList = NULL;
            LONG dpiValue;

            PhCenterWindow(hwndDlg, GetParent(hwndDlg));
            PhSetApplicationWindowIcon(hwndDlg);

            dpiValue = PhGetWindowDpi(hwndDlg);

            context->InactiveWindowHandle = GetDlgItem(hwndDlg, IDC_INACTIVE);
            context->ActiveWindowHandle = GetDlgItem(hwndDlg, IDC_ACTIVE);
            context->SearchInactiveHandle = GetDlgItem(hwndDlg, IDC_SEARCH);
            context->SearchActiveHandle = GetDlgItem(hwndDlg, IDC_FILTER);
            context->HideWindowHandle = GetDlgItem(hwndDlg, IDC_HIDE);
            context->ShowWindowHandle = GetDlgItem(hwndDlg, IDC_SHOW);
            context->MoveUpHandle = GetDlgItem(hwndDlg, IDC_MOVEUP);
            context->MoveDownHandle = GetDlgItem(hwndDlg, IDC_MOVEDOWN);
            context->InactiveListArray = PhCreateList(1);
            context->ActiveListArray = PhCreateList(1);
            context->ControlFont = PhCreateMessageFont(dpiValue); // PhDuplicateFontUpdateDpi(PhTreeWindowFont, PhGetWindowDpi(hwndDlg))

            PhCreateSearchControl(
                hwndDlg,
                context->SearchInactiveHandle,
                PhTranslateUiText(L"Inactive columns..."),
                PhpInactiveColumnsSearchControlCallback,
                context
                );

            PhCreateSearchControl(
                hwndDlg,
                context->SearchActiveHandle,
                PhTranslateUiText(L"Active columns..."),
                PhpActiveColumnsSearchControlCallback,
                context
                );

            ListBox_SetItemHeight(context->InactiveWindowHandle, 0, PhScaleToDisplay(16, dpiValue));
            ListBox_SetItemHeight(context->ActiveWindowHandle, 0, PhScaleToDisplay(16, dpiValue));

            context->DragListMessage = RegisterWindowMessage(DRAGLISTMSGSTRING);
            context->DragItemIndex = LB_ERR;
            context->DragInsertIndex = INT_ERROR;
            MakeDragList(context->InactiveWindowHandle);
            MakeDragList(context->ActiveWindowHandle);

            // Subclass the list boxes (after MakeDragList) for hot tracking.
            context->HotListIndex = LB_ERR;
            PhSetWindowContext(context->InactiveWindowHandle, PH_WINDOW_CONTEXT_DEFAULT, context);
            PhSetWindowContext(context->ActiveWindowHandle, PH_WINDOW_CONTEXT_DEFAULT, context);
            context->InactiveListWindowProc = (WNDPROC)SetWindowLongPtr(context->InactiveWindowHandle, GWLP_WNDPROC, (LONG_PTR)PhpColumnsListBoxWndProc);
            context->ActiveListWindowProc = (WNDPROC)SetWindowLongPtr(context->ActiveWindowHandle, GWLP_WNDPROC, (LONG_PTR)PhpColumnsListBoxWndProc);

            // Each list is a tooltip tool; text is resolved from the hovered stable column ID.
            if (context->ProcessColumns)
            {
                TOOLINFO tool = { sizeof(TOOLINFO) };
                context->TooltipHandle = CreateWindowEx(WS_EX_TOPMOST, TOOLTIPS_CLASS, NULL,
                    WS_POPUP | TTS_ALWAYSTIP | TTS_NOPREFIX, CW_USEDEFAULT, CW_USEDEFAULT,
                    CW_USEDEFAULT, CW_USEDEFAULT, hwndDlg, NULL, PhInstanceHandle, NULL);
                if (context->TooltipHandle)
                {
                    tool.uFlags = TTF_IDISHWND | TTF_SUBCLASS;
                    tool.hwnd = hwndDlg;
                    tool.lpszText = LPSTR_TEXTCALLBACK;
                    tool.uId = (UINT_PTR)context->InactiveWindowHandle;
                    SendMessage(context->TooltipHandle, TTM_ADDTOOL, 0, (LPARAM)&tool);
                    tool.uId = (UINT_PTR)context->ActiveWindowHandle;
                    SendMessage(context->TooltipHandle, TTM_ADDTOOL, 0, (LPARAM)&tool);
                    SendMessage(context->TooltipHandle, TTM_SETMAXTIPWIDTH, 0, PhScaleToDisplay(420, dpiValue));
                }
            }

            Button_Enable(context->HideWindowHandle, FALSE);
            Button_Enable(context->ShowWindowHandle, FALSE);
            Button_Enable(context->MoveUpHandle, FALSE);
            Button_Enable(context->MoveDownHandle, FALSE);

            if (PhEnableThemeSupport)
            {
                context->BrushNormal = CreateSolidBrush(PhThemeWindowBackgroundColor);
                context->BrushHot = CreateSolidBrush(PhThemeWindowHighlightColor);
                context->BrushPushed = CreateSolidBrush(PhThemeWindowHighlight2Color);
                context->BrushHover = CreateSolidBrush(PhThemeWindowBackground2Color);
                context->TextColor = PhThemeWindowTextColor;
            }
            else
            {
                context->BrushNormal = GetSysColorBrush(COLOR_WINDOW);
                context->BrushHot = CreateSolidBrush(RGB(145, 201, 247));
                context->BrushPushed = CreateSolidBrush(RGB(153, 209, 255));
                context->BrushHover = CreateSolidBrush(RGB(229, 243, 255));
                context->TextColor = GetSysColor(COLOR_WINDOWTEXT);
            }

            if (context->Type == PH_CONTROL_TYPE_TREE_NEW)
            {
                PH_TREENEW_COLUMN column;

                count = 0;
                total = TreeNew_GetColumnCount(context->ControlHandle);
                i = 0;

                displayOrderList = PhCreateList(total);

                while (count < total)
                {
                    if (TreeNew_GetColumn(context->ControlHandle, i, &column))
                    {
                        PPH_TREENEW_COLUMN copy;

                        if (column.Fixed)
                        {
                            i++;
                            total--;
                            continue;
                        }

                        copy = PhAllocateCopy(&column, sizeof(PH_TREENEW_COLUMN));
                        PhAddItemList(context->Columns, copy);
                        count++;

                        if (column.Visible)
                        {
                            PhAddItemList(displayOrderList, copy);
                        }
                        else
                        {
                            PhAddItemList(context->InactiveListArray, copy);
                        }
                    }

                    i++;
                }

                qsort_s(displayOrderList->Items, displayOrderList->Count, sizeof(PVOID), PhpColumnsCompareDisplayIndexTn, NULL);
            }

            PhpColumnsResetListBox(
                context->InactiveWindowHandle,
                0,
                context->InactiveListArray,
                PhpInactiveColumnsCompareNameTn
                );

            if (displayOrderList)
            {
                for (i = 0; i < displayOrderList->Count; i++)
                {
                    if (context->Type == PH_CONTROL_TYPE_TREE_NEW)
                    {
                        PPH_TREENEW_COLUMN copy = displayOrderList->Items[i];

                        PhAddItemList(context->ActiveListArray, copy);
                        PhpColumnsInsertItem(context->ActiveWindowHandle, i, copy);
                    }
                }

                PhDereferenceObject(displayOrderList);
            }

            SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_INACTIVE, LBN_SELCHANGE), (LPARAM)context->InactiveWindowHandle);
            SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_ACTIVE, LBN_SELCHANGE), (LPARAM)context->ActiveWindowHandle);

            PhInitializeWindowTheme(hwndDlg, PhEnableThemeSupport);

            PhSetDialogFocus(hwndDlg, GetDlgItem(hwndDlg, IDCANCEL));
        }
        break;
    case WM_DESTROY:
        {
            PhpColumnsSetDragInsert(context, NULL, INT_ERROR);
            PhpColumnsDestroyDragImage(context, hwndDlg);
            if (context->TooltipHandle)
            {
                DestroyWindow(context->TooltipHandle);
                context->TooltipHandle = NULL;
            }

            for (ULONG i = 0; i < context->Columns->Count; i++)
                PhFree(context->Columns->Items[i]);

            if (context->BrushNormal)
                DeleteBrush(context->BrushNormal);
            if (context->BrushHot)
                DeleteBrush(context->BrushHot);
            if (context->BrushPushed)
                DeleteBrush(context->BrushPushed);
            if (context->BrushHover)
                DeleteBrush(context->BrushHover);
            if (context->ControlFont)
                DeleteFont(context->ControlFont);
            if (context->InactiveListArray)
                PhDereferenceObject(context->InactiveListArray);
            if (context->ActiveListArray)
                PhDereferenceObject(context->ActiveListArray);

            PhRemoveWindowContext(hwndDlg, PH_WINDOW_CONTEXT_DEFAULT);
        }
        break;
    case WM_DPICHANGED:
        {
            if (context->ControlFont) DeleteFont(context->ControlFont);
            context->ControlFont = PhCreateMessageFont(LOWORD(wParam));

            if (context->TooltipHandle)
                SendMessage(context->TooltipHandle, TTM_SETMAXTIPWIDTH, 0, PhScaleToDisplay(420, LOWORD(wParam)));
            ListBox_SetItemHeight(context->InactiveWindowHandle, 0, PhScaleToDisplay(16, LOWORD(wParam)));
            ListBox_SetItemHeight(context->ActiveWindowHandle, 0, PhScaleToDisplay(16, LOWORD(wParam)));
        }
        break;
    case WM_NOTIFY:
        {
            LPNMHDR header = (LPNMHDR)lParam;
            if (header->hwndFrom == context->TooltipHandle && header->code == TTN_GETDISPINFO)
            {
                LPNMTTDISPINFO info = (LPNMTTDISPINFO)lParam;
                PPH_TREENEW_COLUMN column = NULL;
                info->lpszText = NULL;
                HWND listHandle = (HWND)header->idFrom;
                POINT point;
                if (context->DragItemIndex == LB_ERR &&
                    (listHandle == context->ActiveWindowHandle || listHandle == context->InactiveWindowHandle) &&
                    GetCursorPos(&point) && ScreenToClient(listHandle, &point))
                {
                    RECT rect;
                    if (GetClientRect(listHandle, &rect) && PtInRect(&rect, point))
                    {
                        LRESULT hit = SendMessage(listHandle, LB_ITEMFROMPOINT, 0, MAKELPARAM(point.x, point.y));
                        LONG index = (LONG)(SHORT)LOWORD(hit);
                        if (HIWORD(hit) == 0 &&
                            ListBox_GetItemRect(listHandle, index, &rect) != LB_ERR && PtInRect(&rect, point))
                            column = PhpColumnsGetItem(listHandle, index);
                    }
                }
                if (column)
                    info->lpszText = (PWSTR)PhpGetProcessColumnDescription(column->Id);
                return TRUE;
            }
        }
        break;
    case WM_COMMAND:
        {
            switch (GET_WM_COMMAND_ID(wParam, lParam))
            {
            case IDCANCEL:
                EndDialog(hwndDlg, IDCANCEL);
                break;
            case IDOK:
                {
                    ULONG i;
                    ULONG orderArraySize;
                    PULONG orderArray;
                    ULONG maxOrder;

                    if (context->Type == PH_CONTROL_TYPE_TREE_NEW)
                    {
                        orderArraySize = (TreeNew_GetColumnCount(context->ControlHandle) + 1) * sizeof(ULONG);
                        orderArray = PhAllocateStack(orderArraySize);

                        memset(orderArray, 0, orderArraySize);
                        maxOrder = 0;

                        // Apply visibility settings and build the order array.

                        TreeNew_SetRedraw(context->ControlHandle, FALSE);

                        for (i = 0; i < context->Columns->Count; i++)
                        {
                            PPH_TREENEW_COLUMN column = context->Columns->Items[i];
                            ULONG index;

                            index = PhpColumnsIndexOf(context->ActiveListArray, column);
                            column->Visible = index != ULONG_MAX;

                            TreeNew_SetColumn(context->ControlHandle, TN_COLUMN_FLAG_VISIBLE, column);

                            if (column->Visible)
                            {
                                orderArray[index] = column->Id;

                                if (maxOrder < index + 1)
                                    maxOrder = index + 1;
                            }
                        }

                        // Apply display order.
                        TreeNew_SetColumnOrderArray(context->ControlHandle, maxOrder, orderArray);

                        TreeNew_SetRedraw(context->ControlHandle, TRUE);

                        InvalidateRect(context->ControlHandle, NULL, FALSE);

                        PhFreeStack(orderArray);
                    }

                    EndDialog(hwndDlg, IDOK);
                }
                break;
            case IDC_INACTIVE:
                {
                    switch (GET_WM_COMMAND_CMD(wParam, lParam))
                    {
                    case LBN_DBLCLK:
                        {
                            SendMessage(hwndDlg, WM_COMMAND, IDC_SHOW, 0);
                        }
                        break;
                    case LBN_SELCHANGE:
                        {
                            LONG sel = ListBox_GetCurSel(context->InactiveWindowHandle);

                            EnableWindow(context->ShowWindowHandle, sel != LB_ERR);
                        }
                        break;
                    }
                }
                break;
            case IDC_ACTIVE:
                {
                    switch (GET_WM_COMMAND_CMD(wParam, lParam))
                    {
                    case LBN_DBLCLK:
                        {
                            SendMessage(hwndDlg, WM_COMMAND, IDC_HIDE, 0);
                        }
                        break;
                    case LBN_SELCHANGE:
                        {
                            LONG sel = ListBox_GetCurSel(context->ActiveWindowHandle);
                            LONG count = ListBox_GetCount(context->ActiveWindowHandle);

                            EnableWindow(context->HideWindowHandle, sel != LB_ERR);
                            EnableWindow(context->MoveUpHandle, sel != LB_ERR && sel != 0);
                            EnableWindow(context->MoveDownHandle, sel != LB_ERR && sel != count - 1);
                        }
                        break;
                    }
                }
                break;
            case IDC_SHOW:
                {
                    PhpColumnsShowItem(context, ListBox_GetCurSel(context->InactiveWindowHandle), INT_ERROR);

                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_INACTIVE, LBN_SELCHANGE), (LPARAM)context->InactiveWindowHandle);
                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_ACTIVE, LBN_SELCHANGE), (LPARAM)context->ActiveWindowHandle);
                }
                break;
            case IDC_HIDE:
                {
                    PhpColumnsHideItem(context, ListBox_GetCurSel(context->ActiveWindowHandle));

                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_INACTIVE, LBN_SELCHANGE), (LPARAM)context->InactiveWindowHandle);
                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_ACTIVE, LBN_SELCHANGE), (LPARAM)context->ActiveWindowHandle);
                }
                break;
            case IDC_MOVEUP:
                {
                    LONG sel = ListBox_GetCurSel(context->ActiveWindowHandle);

                    if (sel != LB_ERR)
                        PhpColumnsMoveActiveItem(context, sel, sel - 1);
                }
                break;
            case IDC_MOVEDOWN:
                {
                    LONG sel = ListBox_GetCurSel(context->ActiveWindowHandle);

                    if (sel != LB_ERR)
                        PhpColumnsMoveActiveItem(context, sel, sel + 2);
                }
                break;
            }
        }
        break;
     case WM_DRAWITEM:
         {
             LPDRAWITEMSTRUCT drawInfo = (LPDRAWITEMSTRUCT)lParam;

             if (
                 drawInfo->hwndItem == context->InactiveWindowHandle ||
                 drawInfo->hwndItem == context->ActiveWindowHandle
                 )
             {
                 HDC bufferDc;
                 HBITMAP bufferBitmap;
                 HBITMAP oldBufferBitmap;
                 PPH_STRING string;
                 RECT bufferRect =
                 {
                     0, 0,
                     drawInfo->rcItem.right - drawInfo->rcItem.left,
                     drawInfo->rcItem.bottom - drawInfo->rcItem.top
                 };
                 BOOLEAN isSelected = (drawInfo->itemState & ODS_SELECTED) == ODS_SELECTED;
                 BOOLEAN isFocused = (drawInfo->itemState & ODS_FOCUS) == ODS_FOCUS;
                 BOOLEAN isHot =
                     drawInfo->hwndItem == context->HotListHandle &&
                     (LONG)drawInfo->itemID == context->HotListIndex;

                 if (drawInfo->itemID == LB_ERR)
                     break;

                 string = PhGetListBoxString(drawInfo->hwndItem, drawInfo->itemID);

                 if (PhIsNullOrEmptyString(string))
                 {
                     PhClearReference(&string);
                     break;
                 }

                 bufferDc = CreateCompatibleDC(drawInfo->hDC);
                 bufferBitmap = PhCreateDIBSection(drawInfo->hDC, PHBF_TOPDOWNDIB, bufferRect.right, bufferRect.bottom, NULL);
                 oldBufferBitmap = SelectBitmap(bufferDc, bufferBitmap);

                 SelectFont(bufferDc, context->ControlFont);
                 SetBkMode(bufferDc, TRANSPARENT);

                 if (isSelected || isFocused)
                 {
                     FillRect(bufferDc, &bufferRect, context->BrushHot);
                     //FrameRect(bufferDc, &bufferRect, PhGetStockBrush(BLACK_BRUSH));
                     SetTextColor(bufferDc, context->TextColor);
                 }
                 else if (isHot)
                 {
                     FillRect(bufferDc, &bufferRect, context->BrushHover);
                     SetTextColor(bufferDc, context->TextColor);
                 }
                 else
                 {
                     FillRect(bufferDc, &bufferRect, context->BrushNormal);
                     //FrameRect(bufferDc, &bufferRect, GetSysColorBrush(COLOR_HIGHLIGHTTEXT));
                     SetTextColor(bufferDc, context->TextColor);
                 }

                 bufferRect.left += 5;
                 DrawText(
                     bufferDc,
                     string->Buffer,
                     (UINT)string->Length / sizeof(WCHAR),
                     &bufferRect,
                     DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS | DT_NOCLIP
                     );
                 bufferRect.left -= 5;

                 BitBlt(
                     drawInfo->hDC,
                     drawInfo->rcItem.left,
                     drawInfo->rcItem.top,
                     drawInfo->rcItem.right,
                     drawInfo->rcItem.bottom,
                     bufferDc,
                     0,
                     0,
                     SRCCOPY
                     );

                 PhpColumnsDrawDragInsert(context, drawInfo);

                 SelectBitmap(bufferDc, oldBufferBitmap);
                 DeleteBitmap(bufferBitmap);
                 DeleteDC(bufferDc);
                 PhClearReference(&string);

                 return TRUE;
             }
         }
         break;
     case WM_CTLCOLORBTN:
         return HANDLE_WM_CTLCOLORBTN(hwndDlg, wParam, lParam, PhWindowThemeControlColor);
     case WM_CTLCOLORDLG:
         return HANDLE_WM_CTLCOLORDLG(hwndDlg, wParam, lParam, PhWindowThemeControlColor);
     case WM_CTLCOLORSTATIC:
         return HANDLE_WM_CTLCOLORSTATIC(hwndDlg, wParam, lParam, PhWindowThemeControlColor);
    }

    if (context->DragListMessage && uMsg == context->DragListMessage)
    {
        LPDRAGLISTINFO dragInfo = (LPDRAGLISTINFO)lParam;
        LRESULT result = 0;

        switch (dragInfo->uNotification)
        {
        case DL_BEGINDRAG:
            {
                LONG index = LBItemFromPt(dragInfo->hWnd, dragInfo->ptCursor, FALSE);

                if (index != INT_ERROR)
                {
                    POINT dialogPoint;
                    POINT hotspot;
                    HIMAGELIST imageList;
                    LONG imageWidth;
                    LONG imageHeight;
                    BOOLEAN dragStarted = FALSE;

                    // Clear the hot item before the drag image is shown so nothing repaints underneath it.
                    PhpColumnsSetHotItem(context, NULL, LB_ERR);

                    context->DragSourceHandle = dragInfo->hWnd;
                    context->DragItemIndex = index;
                    ListBox_SetCurSel(dragInfo->hWnd, index);

                    UpdateWindow(dragInfo->hWnd);
                    UpdateWindow(context->InactiveWindowHandle);
                    UpdateWindow(context->ActiveWindowHandle);

                    if ((imageList = PhpColumnsCreateDragImage(
                        dragInfo->hWnd,
                        index,
                        dragInfo->ptCursor,
                        &hotspot,
                        &imageWidth,
                        &imageHeight
                        )))
                    {
                        if (PhpColumnsGetDragWindowPoint(hwndDlg, dragInfo->ptCursor, &dialogPoint))
                        {
                            PhpColumnsConstrainDragWindowPoint(
                                hwndDlg,
                                imageWidth,
                                imageHeight,
                                hotspot,
                                &dialogPoint
                                );

                            if (PhImageListBeginDrag(imageList, 0, hotspot.x, hotspot.y))
                            {
                                dragStarted = TRUE;

                                if (PhImageListDragEnter(hwndDlg, dialogPoint.x, dialogPoint.y))
                                {
                                    context->DragImageList = imageList;
                                    context->DragImageHotspot = hotspot;
                                    context->DragImageWidth = imageWidth;
                                    context->DragImageHeight = imageHeight;
                                }
                            }
                        }
                        if (!context->DragImageList)
                        {
                            if (dragStarted)
                                PhImageListEndDrag();

                            PhImageListDestroy(imageList);
                        }
                    }

                    result = TRUE;
                }
            }
            break;
        case DL_DRAGGING:
            {
                LONG activeIndex = PhpColumnsDragTargetIndex(context->ActiveWindowHandle, dragInfo->ptCursor, TRUE);
                LONG inactiveIndex = PhpColumnsDragTargetIndex(context->InactiveWindowHandle, dragInfo->ptCursor, FALSE);

                if (activeIndex != INT_ERROR)
                {
                    PhpColumnsSetDragInsert(context, context->ActiveWindowHandle, activeIndex);
                    result = DL_MOVECURSOR;
                }
                else if (inactiveIndex != INT_ERROR && context->DragSourceHandle == context->ActiveWindowHandle)
                {
                    // The inactive list is sorted, so there's no insert position to show.
                    PhpColumnsSetDragInsert(context, NULL, INT_ERROR);
                    result = DL_MOVECURSOR;
                }
                else
                {
                    PhpColumnsSetDragInsert(context, NULL, INT_ERROR);
                    result = DL_STOPCURSOR;
                }

                if (context->DragImageList)
                {
                    POINT dialogPoint;

                    if (PhpColumnsGetDragWindowPoint(hwndDlg, dragInfo->ptCursor, &dialogPoint))
                    {
                        PhpColumnsConstrainDragWindowPoint(
                            hwndDlg,
                            context->DragImageWidth,
                            context->DragImageHeight,
                            context->DragImageHotspot,
                            &dialogPoint
                            );
                        PhImageListDragMove(dialogPoint.x, dialogPoint.y);
                    }
                }
            }
            break;
        case DL_DROPPED:
            {
                LONG activeIndex = PhpColumnsDragTargetIndex(context->ActiveWindowHandle, dragInfo->ptCursor, FALSE);
                LONG inactiveIndex = PhpColumnsDragTargetIndex(context->InactiveWindowHandle, dragInfo->ptCursor, FALSE);

                PhpColumnsSetDragInsert(context, NULL, INT_ERROR);
                PhpColumnsDestroyDragImage(context, hwndDlg);

                if (context->DragItemIndex != LB_ERR)
                {
                    if (context->DragSourceHandle == context->ActiveWindowHandle)
                    {
                        if (activeIndex != INT_ERROR)
                            PhpColumnsMoveActiveItem(context, context->DragItemIndex, activeIndex);
                        else if (inactiveIndex != INT_ERROR)
                            PhpColumnsHideItem(context, context->DragItemIndex);
                    }
                    else if (context->DragSourceHandle == context->InactiveWindowHandle)
                    {
                        if (activeIndex != INT_ERROR)
                            PhpColumnsShowItem(context, context->DragItemIndex, activeIndex);
                    }

                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_INACTIVE, LBN_SELCHANGE), (LPARAM)context->InactiveWindowHandle);
                    SendMessage(hwndDlg, WM_COMMAND, MAKEWPARAM(IDC_ACTIVE, LBN_SELCHANGE), (LPARAM)context->ActiveWindowHandle);
                }

                context->DragSourceHandle = NULL;
                context->DragItemIndex = LB_ERR;
            }
            break;
        case DL_CANCELDRAG:
            {
                PhpColumnsSetDragInsert(context, NULL, INT_ERROR);
                PhpColumnsDestroyDragImage(context, hwndDlg);
                context->DragSourceHandle = NULL;
                context->DragItemIndex = LB_ERR;
            }
            break;
        }

        SetWindowLongPtr(hwndDlg, DWLP_MSGRESULT, result);
        return TRUE;
    }

    return FALSE;
}
