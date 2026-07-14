# Keyence.AutoID.SDK - Full API Reference
(Extracted from SR_SDK_8_71/Manual/Keyence.AutoID.SDK_Help.chm)

## Keyence.AutoID.SDK

﻿ Keyence.AutoID.SDK Namespace Keyence.AutoID.SDK Class Library Keyence.AutoID.SDK Namespace   Classes 
 Class Description LiveviewForm 
 UserControl which shows recent image received from a target SR.
 NicSearchResult 
 A result of searching process of Network Interface Card (NIC) by ReaderSearcher.ListUpNic Method. 
 ReaderAccessor 
 Reader Access Functions. (receive read data, execute command operation, handle reader's file)
 ReaderSearcher 
 SR Search Functions. (search SR in current networks, get SR information)
 ReaderSearchResult 
 A result of ReaderSearcher.Start Method.
 Enumerations 
 Enumeration Description ErrorCode 
 Error Code of ReaderAccessor.
 LiveviewForm ImageBinningType 
 Type of Image Binning.
 LiveviewForm ImageFormatType 
 Image File Format.

### ErrorCode Enumeration

﻿ ErrorCode Enumeration Keyence.AutoID.SDK Class Library ErrorCode Enumeration 
 Error Code of ReaderAccessor.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public enum ErrorCode Public Enumeration ErrorCode Members 
 Member name Value Description None 0 
 No Error.
 AlreadyOpen 1 
 AlreadyOpen.
 Closed 2 
 Closed.
 OpenFailed 3 
 OpenFailed.
 HeadFailed 4 
 HeadFailed.
 Timeout 5 
 Timeout.
 SendFailed 6 
 SendFailed.
 BeginReceiveFailed 7 
 BeginReceiveFailed.
 IpAddressInvalidArgument 8 
 IpAddressInvalidArgument.
 IpAddressUsed 9 
 IpAddressUsed.
 CommandPortInvalidArgument 10 
 CommandPortInvalidArgument.
 DataPortInvalidArgument 11 
 DataPortInvalidArgument.
 CommandInvalidArgument 12 
 CommandInvalidArgument.
 CommandTimeoutInvalidArgument 13 
 CommandTimeoutInvalidArgument.
 SocketAddressUsed 14 
 SocketAddressUsed.
 SocketConnectionReset 15 
 SocketConnectionReset.
 FtpServiceUnavailable 421 
 FtpServiceUnavailable.
 FtpCannotOpenDataConnection 425 
 FtpCannotOpenDataConnection.
 FtpDataConnectionDisconnected 426 
 FtpDataConnectionDisconnected.
 FtpFileBusy 450 
 FtpFileBusy.
 FtpActionAborted 451 
 FtpActionAborted.
 FtpDiskFull 452 
 FtpDiskFull.
 FtpCommandUnrecognized 500 
 FtpCommandUnrecognized.
 FtpInvalidArgument 501 
 FtpInvalidArgument.
 FtpCommandUnimplemented 502 
 FtpCommandUnimplemented.
 FtpCommandBadSequence 503 
 FtpCommandBadSequence.
 FtpArgumentsUnimplemented 504 
 FtpArgumentsUnimplemented.
 FtpNotLoggedIn 530 
 FtpNotLoggedIn.
 FtpActionFailed 550 
 FtpActionFailed.
 FtpExceededDisk 552 
 FtpExceededDisk.
 FtpFileActionFailed 553 
 FtpFileActionFailed.
 SocketAddressDisabled 10049 
 SocketAddressDisabled.
 SocketConnectionUnreach 10051 
 SocketConnectionUnreach.
 SocketAlreadyConnected 10052 
 SocketAlreadyConnected.
 SocketConnectionTimeout 10053 
 SocketConnectionTimeout.
 SocketConnectionRefused 10054 
 SocketConnectionRefused.
 UnexpectedError 10055 
 UnexpectedError.
 See Also Reference Keyence.AutoID.SDK Namespace

### LiveviewForm Class

﻿ LiveviewForm Class Keyence.AutoID.SDK Class Library LiveviewForm Class 
 UserControl which shows recent image received from a target SR.
 Inheritance Hierarchy System Object    System MarshalByRefObject      System.ComponentModel Component        System.Windows.Forms Control          System.Windows.Forms ScrollableControl            System.Windows.Forms ContainerControl              System.Windows.Forms UserControl                Keyence.AutoID.SDK LiveviewForm 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public class LiveviewForm : UserControl , 
 IDisposable Public Class LiveviewForm 
 Inherits UserControl 
 Implements IDisposable The LiveviewForm type exposes the following members. Constructors 
 Name Description LiveviewForm 
 This class represents LiveviewForm.
 Top Properties 
 Name Description AccessibilityObject (Inherited from Control .) AccessibleDefaultActionDescription (Inherited from Control .) AccessibleDescription (Inherited from Control .) AccessibleName (Inherited from Control .) AccessibleRole (Inherited from Control .) ActiveControl (Inherited from ContainerControl .) AllowDrop (Inherited from Control .) Anchor (Inherited from Control .) AutoScaleDimensions (Inherited from ContainerControl .) AutoScaleFactor (Inherited from ContainerControl .) AutoScaleMode (Inherited from ContainerControl .) AutoScroll (Inherited from ScrollableControl .) AutoScrollMargin (Inherited from ScrollableControl .) AutoScrollMinSize (Inherited from ScrollableControl .) AutoScrollOffset (Inherited from Control .) AutoScrollPosition (Inherited from ScrollableControl .) AutoSize (Inherited from UserControl .) AutoSizeMode (Inherited from UserControl .) AutoValidate (Inherited from UserControl .) BackColor (Inherited from Control .) BackgroundImage (Inherited from Control .) BackgroundImageLayout (Inherited from Control .) BindingContext (Inherited from ContainerControl .) BinningType 
 Image Binning Settings. Default is OneQuarter. 
 This property is applied when calling “BeginReceive” method.
 BorderStyle (Inherited from UserControl .) Bottom (Inherited from Control .) Bounds (Inherited from Control .) CanEnableIme (Inherited from ContainerControl .) CanFocus (Inherited from Control .) CanRaiseEvents (Inherited from Control .) CanSelect (Inherited from Control .) Capture (Inherited from Control .) CausesValidation (Inherited from Control .) ClientRectangle (Inherited from Control .) ClientSize (Inherited from Control .) CompanyName (Inherited from Control .) Container (Inherited from Component .) ContainsFocus (Inherited from Control .) ContextMenu (Inherited from Control .) ContextMenuStrip (Inherited from Control .) Controls (Inherited from Control .) Created (Inherited from Control .) CreateParams (Inherited from UserControl .) CurrentAutoScaleDimensions (Inherited from ContainerControl .) Cursor (Inherited from Control .) DataBindings (Inherited from Control .) DefaultCursor (Inherited from Control .) DefaultImeMode (Inherited from Control .) DefaultMargin (Inherited from Control .) DefaultMaximumSize (Inherited from Control .) DefaultMinimumSize (Inherited from Control .) DefaultPadding (Inherited from Control .) DefaultSize (Inherited from UserControl .) DesignMode (Inherited from Component .) DisplayRectangle (Inherited from ScrollableControl .) Disposing (Inherited from Control .) Dock (Inherited from Control .) DoubleBuffered (Inherited from Control .) Enabled (Inherited from Control .) Events (Inherited from Component .) Focused (Inherited from Control .) Font (Inherited from Control .) FontHeight (Inherited from Control .) ForeColor (Inherited from Control .) Handle (Inherited from Control .) HasChildren (Inherited from Control .) Height (Inherited from Control .) HorizontalScroll (Inherited from ScrollableControl .) HScroll (Inherited from ScrollableControl .) ImageFormat 
 Image Format Type. Default is Jpeg. 
 This property is applied when calling “BeginReceive” method.
 ImageQuality 
 Image Quality Settings. 1(Low quality)-10(High quality). Default is 5. 
 This is valid for Jpeg Format only. This property is applied when calling “BeginReceive” method.
 ImeMode (Inherited from Control .) ImeModeBase (Inherited from Control .) InvokeRequired (Inherited from Control .) IpAddress 
 Target SR IP Address. Default is "192.168.100.100". 
 This property is applied when calling “BeginReceive” method.
 IsAccessible (Inherited from Control .) IsDisposed (Inherited from Control .) IsHandleCreated (Inherited from Control .) IsMirrored (Inherited from Control .) IsReady 
 Operating state of the liveview connection.
 LayoutEngine (Inherited from Control .) Left (Inherited from Control .) Location (Inherited from Control .) Margin (Inherited from Control .) MaximumSize (Inherited from Control .) MinimumSize (Inherited from Control .) Name (Inherited from Control .) Padding (Inherited from Control .) Parent (Inherited from Control .) ParentForm (Inherited from ContainerControl .) PreferredSize (Inherited from Control .) ProductName (Inherited from Control .) ProductVersion (Inherited from Control .) PullTimeSpan 
 Image update interval of liveview (1-65535ms). Default is 100. 
 Improvement can be expected by increasing this value in the case where drawing update is delayed in the case of high communication load such as when connecting multiple devices. 
 This property is applied when calling “BeginReceive” method.
 RecreatingHandle (Inherited from Control .) Region (Inherited from Control .) RenderRightToLeft Obsolete. (Inherited from Control .) ResizeRedraw (Inherited from Control .) Right (Inherited from Control .) RightToLeft (Inherited from Control .) ScaleChildren (Inherited from Control .) ShowFocusCues (Inherited from Control .) ShowKeyboardCues (Inherited from Control .) Site (Inherited from Control .) Size (Inherited from Control .) TabIndex (Inherited from Control .) TabStop (Inherited from Control .) Tag (Inherited from Control .) TimeoutMs 
 Reconnection attempt interval time when liveview is disconnected (1-65535 ms). Default is 2000. 
 This property is applied when calling “BeginReceive” method.
 Top (Inherited from Control .) TopLevelControl (Inherited from Control .) UseWaitCursor (Inherited from Control .) VerticalScroll (Inherited from ScrollableControl .) Visible (Inherited from Control .) VScroll (Inherited from ScrollableControl .) Width (Inherited from Control .) Top Methods 
 Name Description AccessibilityNotifyClients(AccessibleEvents, Int32) (Inherited from Control .) AccessibilityNotifyClients(AccessibleEvents, Int32, Int32) (Inherited from Control .) AdjustFormScrollbars (Inherited from ContainerControl .) BeginInvoke(Delegate) (Inherited from Control .) BeginInvoke(Delegate, Object ) (Inherited from Control .) BeginReceive 
 Start receiving images from a SR.
 BringToFront (Inherited from Control .) Contains (Inherited from Control .) CreateAccessibilityInstance (Inherited from Control .) CreateControl (Inherited from Control .) CreateControlsInstance (Inherited from Control .) CreateGraphics (Inherited from Control .) CreateHandle (Inherited from Control .) CreateObjRef (Inherited from MarshalByRefObject .) DefWndProc (Inherited from Control .) DestroyHandle (Inherited from Control .) Dispose (Inherited from Component .) Dispose(Boolean) 
 Releases the resources used by the LiveviewForm.
 (Overrides ContainerControl Dispose(Boolean) .) DoDragDrop (Inherited from Control .) DownloadRecentImage 
 Download recent liveview image to destination file path.
 DrawToBitmap (Inherited from Control .) EndInvoke (Inherited from Control .) EndReceive 
 Stop receiving liveview image from a SR.
 Equals (Inherited from Object .) Finalize (Inherited from Component .) FindForm (Inherited from Control .) Focus (Inherited from Control .) GetAccessibilityObjectById (Inherited from Control .) GetAutoSizeMode (Inherited from Control .) GetChildAtPoint(Point) (Inherited from Control .) GetChildAtPoint(Point, GetChildAtPointSkip) (Inherited from Control .) GetContainerControl (Inherited from Control .) GetHashCode (Inherited from Object .) GetLifetimeService (Inherited from MarshalByRefObject .) GetNextControl (Inherited from Control .) GetPreferredSize (Inherited from Control .) GetScaledBounds (Inherited from Control .) GetScrollState (Inherited from ScrollableControl .) GetService (Inherited from Component .) GetStyle (Inherited from Control .) GetTopLevel (Inherited from Control .) GetType (Inherited from Object .) Hide (Inherited from Control .) InitializeLifetimeService (Inherited from MarshalByRefObject .) InitLayout (Inherited from Control .) Invalidate (Inherited from Control .) Invalidate(Boolean) (Inherited from Control .) Invalidate(Rectangle) (Inherited from Control .) Invalidate(Region) (Inherited from Control .) Invalidate(Rectangle, Boolean) (Inherited from Control .) Invalidate(Region, Boolean) (Inherited from Control .) Invoke(Delegate) (Inherited from Control .) Invoke(Delegate, Object ) (Inherited from Control .) InvokeGotFocus (Inherited from Control .) InvokeLostFocus (Inherited from Control .) InvokeOnClick (Inherited from Control .) InvokePaint (Inherited from Control .) InvokePaintBackground (Inherited from Control .) IsInputChar (Inherited from Control .) IsInputKey (Inherited from Control .) MemberwiseClone (Inherited from Object .) MemberwiseClone(Boolean) (Inherited from MarshalByRefObject .) NotifyInvalidate (Inherited from Control .) OnAutoSizeChanged (Inherited from Control .) OnAutoValidateChanged (Inherited from ContainerControl .) OnBackColorChanged (Inherited from Control .) OnBackgroundImageChanged (Inherited from Control .) OnBackgroundImageLayoutChanged (Inherited from Control .) OnBindingContextChanged (Inherited from Control .) OnCausesValidationChanged (Inherited from Control .) OnChangeUICues (Inherited from Control .) OnClick (Inherited from Control .) OnClientSizeChanged (Inherited from Control .) OnContextMenuChanged (Inherited from Control .) OnContextMenuStripChanged (Inherited from Control .) OnControlAdded (Inherited from Control .) OnControlRemoved (Inherited from Control .) OnCreateControl (Inherited from UserControl .) OnCursorChanged (Inherited from Control .) OnDockChanged (Inherited from Control .) OnDoubleClick (Inherited from Control .) OnDragDrop (Inherited from Control .) OnDragEnter (Inherited from Control .) OnDragLeave (Inherited from Control .) OnDragOver (Inherited from Control .) OnEnabledChanged (Inherited from Control .) OnEnter (Inherited from Control .) OnFontChanged (Inherited from ContainerControl .) OnForeColorChanged (Inherited from Control .) OnGiveFeedback (Inherited from Control .) OnGotFocus (Inherited from Control .) OnHandleCreated (Inherited from Control .) OnHandleDestroyed (Inherited from Control .) OnHelpRequested (Inherited from Control .) OnImeModeChanged (Inherited from Control .) OnInvalidated (Inherited from Control .) OnKeyDown (Inherited from Control .) OnKeyPress (Inherited from Control .) OnKeyUp (Inherited from Control .) OnLayout (Inherited from ContainerControl .) OnLeave (Inherited from Control .) OnLoad (Inherited from UserControl .) OnLocationChanged (Inherited from Control .) OnLostFocus (Inherited from Control .) OnMarginChanged (Inherited from Control .) OnMouseCaptureChanged (Inherited from Control .) OnMouseClick (Inherited from Control .) OnMouseDoubleClick (Inherited from Control .) OnMouseDown (Inherited from UserControl .) OnMouseEnter (Inherited from Control .) OnMouseHover (Inherited from Control .) OnMouseLeave (Inherited from Control .) OnMouseMove (Inherited from Control .) OnMouseUp (Inherited from Control .) OnMouseWheel (Inherited from ScrollableControl .) OnMove (Inherited from Control .) OnNotifyMessage (Inherited from Control .) OnPaddingChanged (Inherited from ScrollableControl .) OnPaint (Inherited from Control .) OnPaintBackground (Inherited from ScrollableControl .) OnParentBackColorChanged (Inherited from Control .) OnParentBackgroundImageChanged (Inherited from Control .) OnParentBindingContextChanged (Inherited from Control .) OnParentChanged (Inherited from ContainerControl .) OnParentCursorChanged (Inherited from Control .) OnParentEnabledChanged (Inherited from Control .) OnParentFontChanged (Inherited from Control .) OnParentForeColorChanged (Inherited from Control .) OnParentRightToLeftChanged (Inherited from Control .) OnParentVisibleChanged (Inherited from Control .) OnPreviewKeyDown (Inherited from Control .) OnPrint (Inherited from Control .) OnQueryContinueDrag (Inherited from Control .) OnRegionChanged (Inherited from Control .) OnResize (Inherited from UserControl .) OnRightToLeftChanged (Inherited from ScrollableControl .) OnScroll (Inherited from ScrollableControl .) OnSizeChanged (Inherited from Control .) OnStyleChanged (Inherited from Control .) OnSystemColorsChanged (Inherited from Control .) OnTabIndexChanged (Inherited from Control .) OnTabStopChanged (Inherited from Control .) OnTextChanged (Inherited from Control .) OnValidated (Inherited from Control .) OnValidating (Inherited from Control .) OnVisibleChanged (Inherited from ScrollableControl .) PerformAutoScale (Inherited from ContainerControl .) PerformLayout (Inherited from Control .) PerformLayout(Control, String) (Inherited from Control .) PointToClient (Inherited from Control .) PointToScreen (Inherited from Control .) PreProcessControlMessage (Inherited from Control .) PreProcessMessage (Inherited from Control .) ProcessCmdKey (Inherited from ContainerControl .) ProcessDialogChar (Inherited from ContainerControl .) ProcessDialogKey (Inherited from ContainerControl .) ProcessKeyEventArgs (Inherited from Control .) ProcessKeyMessage (Inherited from Control .) ProcessKeyPreview (Inherited from Control .) ProcessMnemonic (Inherited from ContainerControl .) ProcessTabKey (Inherited from ContainerControl .) RaiseDragEvent (Inherited from Control .) RaiseKeyEvent (Inherited from Control .) RaiseMouseEvent (Inherited from Control .) RaisePaintEvent (Inherited from Control .) RecreateHandle (Inherited from Control .) RectangleToClient (Inherited from Control .) RectangleToScreen (Inherited from Control .) Refresh (Inherited from Control .) ResetMouseEventArgs (Inherited from Control .) ResetText (Inherited from Control .) ResumeLayout (Inherited from Control .) ResumeLayout(Boolean) (Inherited from Control .) RtlTranslateAlignment(ContentAlignment) (Inherited from Control .) RtlTranslateAlignment(HorizontalAlignment) (Inherited from Control .) RtlTranslateAlignment(LeftRightAlignment) (Inherited from Control .) RtlTranslateContent (Inherited from Control .) RtlTranslateHorizontal (Inherited from Control .) RtlTranslateLeftRight (Inherited from Control .) Scale (Inherited from Control .) ScaleControl (Inherited from ScrollableControl .) ScrollControlIntoView (Inherited from ScrollableControl .) ScrollToControl (Inherited from ScrollableControl .) Select (Inherited from Control .) Select(Boolean, Boolean) (Inherited from ContainerControl .) SelectNextControl (Inherited from Control .) SendToBack (Inherited from Control .) SetAutoScrollMargin (Inherited from ScrollableControl .) SetAutoSizeMode (Inherited from Control .) SetBounds(Int32, Int32, Int32, Int32) (Inherited from Control .) SetBounds(Int32, Int32, Int32, Int32, BoundsSpecified) (Inherited from Control .) SetBoundsCore (Inherited from Control .) SetClientSizeCore (Inherited from Control .) SetDisplayRectLocation (Inherited from ScrollableControl .) SetScrollState (Inherited from ScrollableControl .) SetStyle (Inherited from Control .) SetTopLevel (Inherited from Control .) SetVisibleCore (Inherited from Control .) Show (Inherited from Control .) SizeFromClientSize (Inherited from Control .) SuspendLayout (Inherited from Control .) ToString (Inherited from Component .) Update (Inherited from Control .) UpdateBounds (Inherited from Control .) UpdateBounds(Int32, Int32, Int32, Int32) (Inherited from Control .) UpdateBounds(Int32, Int32, Int32, Int32, Int32, Int32) (Inherited from Control .) UpdateDefaultButton (Inherited from ContainerControl .) UpdateStyles (Inherited from Control .) UpdateZOrder (Inherited from Control .) Validate (Inherited from ContainerControl .) Validate(Boolean) (Inherited from ContainerControl .) ValidateChildren (Inherited from UserControl .) ValidateChildren(ValidationConstraints) (Inherited from UserControl .) WndProc (Inherited from UserControl .) Top Events 
 Name Description AutoSizeChanged (Inherited from UserControl .) AutoValidateChanged (Inherited from UserControl .) BackColorChanged (Inherited from Control .) BackgroundImageChanged (Inherited from Control .) BackgroundImageLayoutChanged (Inherited from Control .) BindingContextChanged (Inherited from Control .) CausesValidationChanged (Inherited from Control .) ChangeUICues (Inherited from Control .) Click (Inherited from Control .) ClientSizeChanged (Inherited from Control .) ContextMenuChanged (Inherited from Control .) ContextMenuStripChanged (Inherited from Control .) ControlAdded (Inherited from Control .) ControlRemoved (Inherited from Control .) CursorChanged (Inherited from Control .) Disposed (Inherited from Component .) DockChanged (Inherited from Control .) DoubleClick (Inherited from Control .) DragDrop (Inherited from Control .) DragEnter (Inherited from Control .) DragLeave (Inherited from Control .) DragOver (Inherited from Control .) EnabledChanged (Inherited from Control .) Enter (Inherited from Control .) FontChanged (Inherited from Control .) ForeColorChanged (Inherited from Control .) GiveFeedback (Inherited from Control .) GotFocus (Inherited from Control .) HandleCreated (Inherited from Control .) HandleDestroyed (Inherited from Control .) HelpRequested (Inherited from Control .) ImeModeChanged (Inherited from Control .) Invalidated (Inherited from Control .) KeyDown (Inherited from Control .) KeyPress (Inherited from Control .) KeyUp (Inherited from Control .) Layout (Inherited from Control .) Leave (Inherited from Control .) Load (Inherited from UserControl .) LocationChanged (Inherited from Control .) LostFocus (Inherited from Control .) MarginChanged (Inherited from Control .) MouseCaptureChanged (Inherited from Control .) MouseClick (Inherited from Control .) MouseDoubleClick (Inherited from Control .) MouseDown (Inherited from Control .) MouseEnter (Inherited from Control .) MouseHover (Inherited from Control .) MouseLeave (Inherited from Control .) MouseMove (Inherited from Control .) MouseUp (Inherited from Control .) MouseWheel (Inherited from Control .) Move (Inherited from Control .) PaddingChanged (Inherited from Control .) Paint (Inherited from Control .) ParentChanged (Inherited from Control .) PreviewKeyDown (Inherited from Control .) QueryAccessibilityHelp (Inherited from Control .) QueryContinueDrag (Inherited from Control .) RegionChanged (Inherited from Control .) Resize (Inherited from Control .) RightToLeftChanged (Inherited from Control .) Scroll (Inherited from ScrollableControl .) SizeChanged (Inherited from Control .) StyleChanged (Inherited from Control .) SystemColorsChanged (Inherited from Control .) TabIndexChanged (Inherited from Control .) TabStopChanged (Inherited from Control .) TextChanged (Inherited from Control .) Validated (Inherited from Control .) Validating (Inherited from Control .) VisibleChanged (Inherited from Control .) Top See Also Reference Keyence.AutoID.SDK Namespace

#### LiveviewForm Constructor 

﻿ LiveviewForm Constructor Keyence.AutoID.SDK Class Library LiveviewForm Constructor 
 This class represents LiveviewForm.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public LiveviewForm () Public Sub New See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

#### LiveviewForm Properties

﻿ LiveviewForm Properties Keyence.AutoID.SDK Class Library LiveviewForm Properties The LiveviewForm type exposes the following members. Properties 
 Name Description AccessibilityObject (Inherited from Control .) AccessibleDefaultActionDescription (Inherited from Control .) AccessibleDescription (Inherited from Control .) AccessibleName (Inherited from Control .) AccessibleRole (Inherited from Control .) ActiveControl (Inherited from ContainerControl .) AllowDrop (Inherited from Control .) Anchor (Inherited from Control .) AutoScaleDimensions (Inherited from ContainerControl .) AutoScaleFactor (Inherited from ContainerControl .) AutoScaleMode (Inherited from ContainerControl .) AutoScroll (Inherited from ScrollableControl .) AutoScrollMargin (Inherited from ScrollableControl .) AutoScrollMinSize (Inherited from ScrollableControl .) AutoScrollOffset (Inherited from Control .) AutoScrollPosition (Inherited from ScrollableControl .) AutoSize (Inherited from UserControl .) AutoSizeMode (Inherited from UserControl .) AutoValidate (Inherited from UserControl .) BackColor (Inherited from Control .) BackgroundImage (Inherited from Control .) BackgroundImageLayout (Inherited from Control .) BindingContext (Inherited from ContainerControl .) BinningType 
 Image Binning Settings. Default is OneQuarter. 
 This property is applied when calling “BeginReceive” method.
 BorderStyle (Inherited from UserControl .) Bottom (Inherited from Control .) Bounds (Inherited from Control .) CanEnableIme (Inherited from ContainerControl .) CanFocus (Inherited from Control .) CanRaiseEvents (Inherited from Control .) CanSelect (Inherited from Control .) Capture (Inherited from Control .) CausesValidation (Inherited from Control .) ClientRectangle (Inherited from Control .) ClientSize (Inherited from Control .) CompanyName (Inherited from Control .) Container (Inherited from Component .) ContainsFocus (Inherited from Control .) ContextMenu (Inherited from Control .) ContextMenuStrip (Inherited from Control .) Controls (Inherited from Control .) Created (Inherited from Control .) CreateParams (Inherited from UserControl .) CurrentAutoScaleDimensions (Inherited from ContainerControl .) Cursor (Inherited from Control .) DataBindings (Inherited from Control .) DefaultCursor (Inherited from Control .) DefaultImeMode (Inherited from Control .) DefaultMargin (Inherited from Control .) DefaultMaximumSize (Inherited from Control .) DefaultMinimumSize (Inherited from Control .) DefaultPadding (Inherited from Control .) DefaultSize (Inherited from UserControl .) DesignMode (Inherited from Component .) DisplayRectangle (Inherited from ScrollableControl .) Disposing (Inherited from Control .) Dock (Inherited from Control .) DoubleBuffered (Inherited from Control .) Enabled (Inherited from Control .) Events (Inherited from Component .) Focused (Inherited from Control .) Font (Inherited from Control .) FontHeight (Inherited from Control .) ForeColor (Inherited from Control .) Handle (Inherited from Control .) HasChildren (Inherited from Control .) Height (Inherited from Control .) HorizontalScroll (Inherited from ScrollableControl .) HScroll (Inherited from ScrollableControl .) ImageFormat 
 Image Format Type. Default is Jpeg. 
 This property is applied when calling “BeginReceive” method.
 ImageQuality 
 Image Quality Settings. 1(Low quality)-10(High quality). Default is 5. 
 This is valid for Jpeg Format only. This property is applied when calling “BeginReceive” method.
 ImeMode (Inherited from Control .) ImeModeBase (Inherited from Control .) InvokeRequired (Inherited from Control .) IpAddress 
 Target SR IP Address. Default is "192.168.100.100". 
 This property is applied when calling “BeginReceive” method.
 IsAccessible (Inherited from Control .) IsDisposed (Inherited from Control .) IsHandleCreated (Inherited from Control .) IsMirrored (Inherited from Control .) IsReady 
 Operating state of the liveview connection.
 LayoutEngine (Inherited from Control .) Left (Inherited from Control .) Location (Inherited from Control .) Margin (Inherited from Control .) MaximumSize (Inherited from Control .) MinimumSize (Inherited from Control .) Name (Inherited from Control .) Padding (Inherited from Control .) Parent (Inherited from Control .) ParentForm (Inherited from ContainerControl .) PreferredSize (Inherited from Control .) ProductName (Inherited from Control .) ProductVersion (Inherited from Control .) PullTimeSpan 
 Image update interval of liveview (1-65535ms). Default is 100. 
 Improvement can be expected by increasing this value in the case where drawing update is delayed in the case of high communication load such as when connecting multiple devices. 
 This property is applied when calling “BeginReceive” method.
 RecreatingHandle (Inherited from Control .) Region (Inherited from Control .) RenderRightToLeft Obsolete. (Inherited from Control .) ResizeRedraw (Inherited from Control .) Right (Inherited from Control .) RightToLeft (Inherited from Control .) ScaleChildren (Inherited from Control .) ShowFocusCues (Inherited from Control .) ShowKeyboardCues (Inherited from Control .) Site (Inherited from Control .) Size (Inherited from Control .) TabIndex (Inherited from Control .) TabStop (Inherited from Control .) Tag (Inherited from Control .) TimeoutMs 
 Reconnection attempt interval time when liveview is disconnected (1-65535 ms). Default is 2000. 
 This property is applied when calling “BeginReceive” method.
 Top (Inherited from Control .) TopLevelControl (Inherited from Control .) UseWaitCursor (Inherited from Control .) VerticalScroll (Inherited from ScrollableControl .) Visible (Inherited from Control .) VScroll (Inherited from ScrollableControl .) Width (Inherited from Control .) Top See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### BinningType Property 

﻿ LiveviewForm.BinningType Property Keyence.AutoID.SDK Class Library LiveviewForm BinningType Property 
 Image Binning Settings. Default is OneQuarter. 
 This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public LiveviewForm ImageBinningType BinningType { get ; set ; } Public Property BinningType As LiveviewForm ImageBinningType 
 Get 
 Set Property Value Type:  LiveviewForm ImageBinningType See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### ImageFormat Property 

﻿ LiveviewForm.ImageFormat Property Keyence.AutoID.SDK Class Library LiveviewForm ImageFormat Property 
 Image Format Type. Default is Jpeg. 
 This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public LiveviewForm ImageFormatType ImageFormat { get ; set ; } Public Property ImageFormat As LiveviewForm ImageFormatType 
 Get 
 Set Property Value Type:  LiveviewForm ImageFormatType See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### ImageQuality Property 

﻿ LiveviewForm.ImageQuality Property Keyence.AutoID.SDK Class Library LiveviewForm ImageQuality Property 
 Image Quality Settings. 1(Low quality)-10(High quality). Default is 5. 
 This is valid for Jpeg Format only. This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int ImageQuality { get ; set ; } Public Property ImageQuality As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### IpAddress Property 

﻿ LiveviewForm.IpAddress Property Keyence.AutoID.SDK Class Library LiveviewForm IpAddress Property 
 Target SR IP Address. Default is "192.168.100.100". 
 This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string IpAddress { get ; set ; } Public Property IpAddress As String 
 Get 
 Set Property Value Type:  String See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### IsReady Property 

﻿ LiveviewForm.IsReady Property Keyence.AutoID.SDK Class Library LiveviewForm IsReady Property 
 Operating state of the liveview connection.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool IsReady { get ; } Public ReadOnly Property IsReady As Boolean 
 Get Property Value Type:  Boolean See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### PullTimeSpan Property 

﻿ LiveviewForm.PullTimeSpan Property Keyence.AutoID.SDK Class Library LiveviewForm PullTimeSpan Property 
 Image update interval of liveview (1-65535ms). Default is 100. 
 Improvement can be expected by increasing this value in the case where drawing update is delayed in the case of high communication load such as when connecting multiple devices. 
 This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int PullTimeSpan { get ; set ; } Public Property PullTimeSpan As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### TimeoutMs Property 

﻿ LiveviewForm.TimeoutMs Property Keyence.AutoID.SDK Class Library LiveviewForm TimeoutMs Property 
 Reconnection attempt interval time when liveview is disconnected (1-65535 ms). Default is 2000. 
 This property is applied when calling “BeginReceive” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int TimeoutMs { get ; set ; } Public Property TimeoutMs As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

#### LiveviewForm Methods

﻿ LiveviewForm Methods Keyence.AutoID.SDK Class Library LiveviewForm Methods The LiveviewForm type exposes the following members. Methods 
 Name Description AccessibilityNotifyClients(AccessibleEvents, Int32) (Inherited from Control .) AccessibilityNotifyClients(AccessibleEvents, Int32, Int32) (Inherited from Control .) AdjustFormScrollbars (Inherited from ContainerControl .) BeginInvoke(Delegate) (Inherited from Control .) BeginInvoke(Delegate, Object ) (Inherited from Control .) BeginReceive 
 Start receiving images from a SR.
 BringToFront (Inherited from Control .) Contains (Inherited from Control .) CreateAccessibilityInstance (Inherited from Control .) CreateControl (Inherited from Control .) CreateControlsInstance (Inherited from Control .) CreateGraphics (Inherited from Control .) CreateHandle (Inherited from Control .) CreateObjRef (Inherited from MarshalByRefObject .) DefWndProc (Inherited from Control .) DestroyHandle (Inherited from Control .) Dispose (Inherited from Component .) Dispose(Boolean) 
 Releases the resources used by the LiveviewForm.
 (Overrides ContainerControl Dispose(Boolean) .) DoDragDrop (Inherited from Control .) DownloadRecentImage 
 Download recent liveview image to destination file path.
 DrawToBitmap (Inherited from Control .) EndInvoke (Inherited from Control .) EndReceive 
 Stop receiving liveview image from a SR.
 Equals (Inherited from Object .) Finalize (Inherited from Component .) FindForm (Inherited from Control .) Focus (Inherited from Control .) GetAccessibilityObjectById (Inherited from Control .) GetAutoSizeMode (Inherited from Control .) GetChildAtPoint(Point) (Inherited from Control .) GetChildAtPoint(Point, GetChildAtPointSkip) (Inherited from Control .) GetContainerControl (Inherited from Control .) GetHashCode (Inherited from Object .) GetLifetimeService (Inherited from MarshalByRefObject .) GetNextControl (Inherited from Control .) GetPreferredSize (Inherited from Control .) GetScaledBounds (Inherited from Control .) GetScrollState (Inherited from ScrollableControl .) GetService (Inherited from Component .) GetStyle (Inherited from Control .) GetTopLevel (Inherited from Control .) GetType (Inherited from Object .) Hide (Inherited from Control .) InitializeLifetimeService (Inherited from MarshalByRefObject .) InitLayout (Inherited from Control .) Invalidate (Inherited from Control .) Invalidate(Boolean) (Inherited from Control .) Invalidate(Rectangle) (Inherited from Control .) Invalidate(Region) (Inherited from Control .) Invalidate(Rectangle, Boolean) (Inherited from Control .) Invalidate(Region, Boolean) (Inherited from Control .) Invoke(Delegate) (Inherited from Control .) Invoke(Delegate, Object ) (Inherited from Control .) InvokeGotFocus (Inherited from Control .) InvokeLostFocus (Inherited from Control .) InvokeOnClick (Inherited from Control .) InvokePaint (Inherited from Control .) InvokePaintBackground (Inherited from Control .) IsInputChar (Inherited from Control .) IsInputKey (Inherited from Control .) MemberwiseClone (Inherited from Object .) MemberwiseClone(Boolean) (Inherited from MarshalByRefObject .) NotifyInvalidate (Inherited from Control .) OnAutoSizeChanged (Inherited from Control .) OnAutoValidateChanged (Inherited from ContainerControl .) OnBackColorChanged (Inherited from Control .) OnBackgroundImageChanged (Inherited from Control .) OnBackgroundImageLayoutChanged (Inherited from Control .) OnBindingContextChanged (Inherited from Control .) OnCausesValidationChanged (Inherited from Control .) OnChangeUICues (Inherited from Control .) OnClick (Inherited from Control .) OnClientSizeChanged (Inherited from Control .) OnContextMenuChanged (Inherited from Control .) OnContextMenuStripChanged (Inherited from Control .) OnControlAdded (Inherited from Control .) OnControlRemoved (Inherited from Control .) OnCreateControl (Inherited from UserControl .) OnCursorChanged (Inherited from Control .) OnDockChanged (Inherited from Control .) OnDoubleClick (Inherited from Control .) OnDragDrop (Inherited from Control .) OnDragEnter (Inherited from Control .) OnDragLeave (Inherited from Control .) OnDragOver (Inherited from Control .) OnEnabledChanged (Inherited from Control .) OnEnter (Inherited from Control .) OnFontChanged (Inherited from ContainerControl .) OnForeColorChanged (Inherited from Control .) OnGiveFeedback (Inherited from Control .) OnGotFocus (Inherited from Control .) OnHandleCreated (Inherited from Control .) OnHandleDestroyed (Inherited from Control .) OnHelpRequested (Inherited from Control .) OnImeModeChanged (Inherited from Control .) OnInvalidated (Inherited from Control .) OnKeyDown (Inherited from Control .) OnKeyPress (Inherited from Control .) OnKeyUp (Inherited from Control .) OnLayout (Inherited from ContainerControl .) OnLeave (Inherited from Control .) OnLoad (Inherited from UserControl .) OnLocationChanged (Inherited from Control .) OnLostFocus (Inherited from Control .) OnMarginChanged (Inherited from Control .) OnMouseCaptureChanged (Inherited from Control .) OnMouseClick (Inherited from Control .) OnMouseDoubleClick (Inherited from Control .) OnMouseDown (Inherited from UserControl .) OnMouseEnter (Inherited from Control .) OnMouseHover (Inherited from Control .) OnMouseLeave (Inherited from Control .) OnMouseMove (Inherited from Control .) OnMouseUp (Inherited from Control .) OnMouseWheel (Inherited from ScrollableControl .) OnMove (Inherited from Control .) OnNotifyMessage (Inherited from Control .) OnPaddingChanged (Inherited from ScrollableControl .) OnPaint (Inherited from Control .) OnPaintBackground (Inherited from ScrollableControl .) OnParentBackColorChanged (Inherited from Control .) OnParentBackgroundImageChanged (Inherited from Control .) OnParentBindingContextChanged (Inherited from Control .) OnParentChanged (Inherited from ContainerControl .) OnParentCursorChanged (Inherited from Control .) OnParentEnabledChanged (Inherited from Control .) OnParentFontChanged (Inherited from Control .) OnParentForeColorChanged (Inherited from Control .) OnParentRightToLeftChanged (Inherited from Control .) OnParentVisibleChanged (Inherited from Control .) OnPreviewKeyDown (Inherited from Control .) OnPrint (Inherited from Control .) OnQueryContinueDrag (Inherited from Control .) OnRegionChanged (Inherited from Control .) OnResize (Inherited from UserControl .) OnRightToLeftChanged (Inherited from ScrollableControl .) OnScroll (Inherited from ScrollableControl .) OnSizeChanged (Inherited from Control .) OnStyleChanged (Inherited from Control .) OnSystemColorsChanged (Inherited from Control .) OnTabIndexChanged (Inherited from Control .) OnTabStopChanged (Inherited from Control .) OnTextChanged (Inherited from Control .) OnValidated (Inherited from Control .) OnValidating (Inherited from Control .) OnVisibleChanged (Inherited from ScrollableControl .) PerformAutoScale (Inherited from ContainerControl .) PerformLayout (Inherited from Control .) PerformLayout(Control, String) (Inherited from Control .) PointToClient (Inherited from Control .) PointToScreen (Inherited from Control .) PreProcessControlMessage (Inherited from Control .) PreProcessMessage (Inherited from Control .) ProcessCmdKey (Inherited from ContainerControl .) ProcessDialogChar (Inherited from ContainerControl .) ProcessDialogKey (Inherited from ContainerControl .) ProcessKeyEventArgs (Inherited from Control .) ProcessKeyMessage (Inherited from Control .) ProcessKeyPreview (Inherited from Control .) ProcessMnemonic (Inherited from ContainerControl .) ProcessTabKey (Inherited from ContainerControl .) RaiseDragEvent (Inherited from Control .) RaiseKeyEvent (Inherited from Control .) RaiseMouseEvent (Inherited from Control .) RaisePaintEvent (Inherited from Control .) RecreateHandle (Inherited from Control .) RectangleToClient (Inherited from Control .) RectangleToScreen (Inherited from Control .) Refresh (Inherited from Control .) ResetMouseEventArgs (Inherited from Control .) ResetText (Inherited from Control .) ResumeLayout (Inherited from Control .) ResumeLayout(Boolean) (Inherited from Control .) RtlTranslateAlignment(ContentAlignment) (Inherited from Control .) RtlTranslateAlignment(HorizontalAlignment) (Inherited from Control .) RtlTranslateAlignment(LeftRightAlignment) (Inherited from Control .) RtlTranslateContent (Inherited from Control .) RtlTranslateHorizontal (Inherited from Control .) RtlTranslateLeftRight (Inherited from Control .) Scale (Inherited from Control .) ScaleControl (Inherited from ScrollableControl .) ScrollControlIntoView (Inherited from ScrollableControl .) ScrollToControl (Inherited from ScrollableControl .) Select (Inherited from Control .) Select(Boolean, Boolean) (Inherited from ContainerControl .) SelectNextControl (Inherited from Control .) SendToBack (Inherited from Control .) SetAutoScrollMargin (Inherited from ScrollableControl .) SetAutoSizeMode (Inherited from Control .) SetBounds(Int32, Int32, Int32, Int32) (Inherited from Control .) SetBounds(Int32, Int32, Int32, Int32, BoundsSpecified) (Inherited from Control .) SetBoundsCore (Inherited from Control .) SetClientSizeCore (Inherited from Control .) SetDisplayRectLocation (Inherited from ScrollableControl .) SetScrollState (Inherited from ScrollableControl .) SetStyle (Inherited from Control .) SetTopLevel (Inherited from Control .) SetVisibleCore (Inherited from Control .) Show (Inherited from Control .) SizeFromClientSize (Inherited from Control .) SuspendLayout (Inherited from Control .) ToString (Inherited from Component .) Update (Inherited from Control .) UpdateBounds (Inherited from Control .) UpdateBounds(Int32, Int32, Int32, Int32) (Inherited from Control .) UpdateBounds(Int32, Int32, Int32, Int32, Int32, Int32) (Inherited from Control .) UpdateDefaultButton (Inherited from ContainerControl .) UpdateStyles (Inherited from Control .) UpdateZOrder (Inherited from Control .) Validate (Inherited from ContainerControl .) Validate(Boolean) (Inherited from ContainerControl .) ValidateChildren (Inherited from UserControl .) ValidateChildren(ValidationConstraints) (Inherited from UserControl .) WndProc (Inherited from UserControl .) Top See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### BeginReceive Method 

﻿ LiveviewForm.BeginReceive Method Keyence.AutoID.SDK Class Library LiveviewForm BeginReceive Method 
 Start receiving images from a SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool BeginReceive () Public Function BeginReceive As Boolean Return Value Type:  Boolean return true when start successfully. See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### Dispose Method 

﻿ LiveviewForm.Dispose Method Keyence.AutoID.SDK Class Library LiveviewForm Dispose Method Overload List 
 Name Description Dispose (Inherited from Component .) Dispose(Boolean) 
 Releases the resources used by the LiveviewForm.
 (Overrides ContainerControl Dispose(Boolean) .) Top See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

###### Dispose Method (Boolean)

﻿ LiveviewForm.Dispose Method (Boolean) Keyence.AutoID.SDK Class Library LiveviewForm Dispose Method (Boolean) 
 Releases the resources used by the LiveviewForm.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy protected override void Dispose (
 bool disposing 
) Protected Overrides Sub Dispose ( 
 disposing As Boolean 
) Parameters disposing Type:  System Boolean True to release both managed and unmanaged resources; false to release only unmanaged resources See Also Reference LiveviewForm Class Dispose Overload Keyence.AutoID.SDK Namespace

##### DownloadRecentImage Method 

﻿ LiveviewForm.DownloadRecentImage Method Keyence.AutoID.SDK Class Library LiveviewForm DownloadRecentImage Method 
 Download recent liveview image to destination file path.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool DownloadRecentImage (
 string dstFile 
) Public Function DownloadRecentImage ( 
 dstFile As String 
) As Boolean Parameters dstFile Type:  System String File name of the destination (PC side) Return Value Type:  Boolean return true when recent liveview image was downloaded successfully See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

##### EndReceive Method 

﻿ LiveviewForm.EndReceive Method Keyence.AutoID.SDK Class Library LiveviewForm EndReceive Method 
 Stop receiving liveview image from a SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void EndReceive () Public Sub EndReceive See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

#### LiveviewForm Events

﻿ LiveviewForm Events Keyence.AutoID.SDK Class Library LiveviewForm Events The LiveviewForm type exposes the following members. Events 
 Name Description AutoSizeChanged (Inherited from UserControl .) AutoValidateChanged (Inherited from UserControl .) BackColorChanged (Inherited from Control .) BackgroundImageChanged (Inherited from Control .) BackgroundImageLayoutChanged (Inherited from Control .) BindingContextChanged (Inherited from Control .) CausesValidationChanged (Inherited from Control .) ChangeUICues (Inherited from Control .) Click (Inherited from Control .) ClientSizeChanged (Inherited from Control .) ContextMenuChanged (Inherited from Control .) ContextMenuStripChanged (Inherited from Control .) ControlAdded (Inherited from Control .) ControlRemoved (Inherited from Control .) CursorChanged (Inherited from Control .) Disposed (Inherited from Component .) DockChanged (Inherited from Control .) DoubleClick (Inherited from Control .) DragDrop (Inherited from Control .) DragEnter (Inherited from Control .) DragLeave (Inherited from Control .) DragOver (Inherited from Control .) EnabledChanged (Inherited from Control .) Enter (Inherited from Control .) FontChanged (Inherited from Control .) ForeColorChanged (Inherited from Control .) GiveFeedback (Inherited from Control .) GotFocus (Inherited from Control .) HandleCreated (Inherited from Control .) HandleDestroyed (Inherited from Control .) HelpRequested (Inherited from Control .) ImeModeChanged (Inherited from Control .) Invalidated (Inherited from Control .) KeyDown (Inherited from Control .) KeyPress (Inherited from Control .) KeyUp (Inherited from Control .) Layout (Inherited from Control .) Leave (Inherited from Control .) Load (Inherited from UserControl .) LocationChanged (Inherited from Control .) LostFocus (Inherited from Control .) MarginChanged (Inherited from Control .) MouseCaptureChanged (Inherited from Control .) MouseClick (Inherited from Control .) MouseDoubleClick (Inherited from Control .) MouseDown (Inherited from Control .) MouseEnter (Inherited from Control .) MouseHover (Inherited from Control .) MouseLeave (Inherited from Control .) MouseMove (Inherited from Control .) MouseUp (Inherited from Control .) MouseWheel (Inherited from Control .) Move (Inherited from Control .) PaddingChanged (Inherited from Control .) Paint (Inherited from Control .) ParentChanged (Inherited from Control .) PreviewKeyDown (Inherited from Control .) QueryAccessibilityHelp (Inherited from Control .) QueryContinueDrag (Inherited from Control .) RegionChanged (Inherited from Control .) Resize (Inherited from Control .) RightToLeftChanged (Inherited from Control .) Scroll (Inherited from ScrollableControl .) SizeChanged (Inherited from Control .) StyleChanged (Inherited from Control .) SystemColorsChanged (Inherited from Control .) TabIndexChanged (Inherited from Control .) TabStopChanged (Inherited from Control .) TextChanged (Inherited from Control .) Validated (Inherited from Control .) Validating (Inherited from Control .) VisibleChanged (Inherited from Control .) Top See Also Reference LiveviewForm Class Keyence.AutoID.SDK Namespace

### LiveviewForm.ImageBinningType Enumeration

﻿ LiveviewForm.ImageBinningType Enumeration Keyence.AutoID.SDK Class Library LiveviewForm ImageBinningType Enumeration 
 Type of Image Binning.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public enum ImageBinningType Public Enumeration ImageBinningType Members 
 Member name Value Description None 0 
 No Binning Image.
 OneQuarter 1 
 1/4 Binning Image.
 OneNinth 2 
 1/9 Binning Image.
 OneSixteenth 3 
 1/16 Binning Image.
 See Also Reference Keyence.AutoID.SDK Namespace

### LiveviewForm.ImageFormatType Enumeration

﻿ LiveviewForm.ImageFormatType Enumeration Keyence.AutoID.SDK Class Library LiveviewForm ImageFormatType Enumeration 
 Image File Format.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public enum ImageFormatType Public Enumeration ImageFormatType Members 
 Member name Value Description Bitmap 0 
 Bitmap Image Format.
 Jpeg 1 
 Jpeg Image Format.
 See Also Reference Keyence.AutoID.SDK Namespace

### NicSearchResult Class

﻿ NicSearchResult Class Keyence.AutoID.SDK Class Library NicSearchResult Class 
 A result of searching process of Network Interface Card (NIC) by ReaderSearcher.ListUpNic Method. 
 Inheritance Hierarchy System Object    Keyence.AutoID.SDK NicSearchResult 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public class NicSearchResult Public Class NicSearchResult The NicSearchResult type exposes the following members. Constructors 
 Name Description NicSearchResult 
 This class represents searched Network Interface Card. 
 NicSearchResult(String, String, String, String) 
 This class represents searched Network Interface Card. 
 Top Properties 
 Name Description NicBroadCastIpAddr 
 Broadcast IP address of Network Interface Card.
 NicIpAddr 
 IP address of Network Interface Card.
 NicIpv4Mask 
 IPv4 subnet mask of Network Interface Card.
 NicName 
 Name of Network Interface Card.
 Top Methods 
 Name Description Equals (Inherited from Object .) Finalize (Inherited from Object .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) ToString (Inherited from Object .) Top See Also Reference Keyence.AutoID.SDK Namespace

#### NicSearchResult Constructor 

﻿ NicSearchResult Constructor Keyence.AutoID.SDK Class Library NicSearchResult Constructor Overload List 
 Name Description NicSearchResult 
 This class represents searched Network Interface Card. 
 NicSearchResult(String, String, String, String) 
 This class represents searched Network Interface Card. 
 Top See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

##### NicSearchResult Constructor 

﻿ NicSearchResult Constructor Keyence.AutoID.SDK Class Library NicSearchResult Constructor 
 This class represents searched Network Interface Card. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public NicSearchResult () Public Sub New See Also Reference NicSearchResult Class NicSearchResult Overload Keyence.AutoID.SDK Namespace

##### NicSearchResult Constructor (String, String, String, String)

﻿ NicSearchResult Constructor (String, String, String, String) Keyence.AutoID.SDK Class Library NicSearchResult Constructor (String, String, String, String) 
 This class represents searched Network Interface Card. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public NicSearchResult (
 string name ,
 string ipAddr ,
 string IPv4Mask ,
 string broadcastIpAddr 
) Public Sub New ( 
 name As String ,
 ipAddr As String ,
 IPv4Mask As String ,
 broadcastIpAddr As String 
) Parameters name Type:  System String Name of Network Interface Card. ipAddr Type:  System String IP address of Network Interface Card. IPv4Mask Type:  System String IPv4 subnet mask of Network Interface Card. broadcastIpAddr Type:  System String Broadcast IP address of Network Interface Card. See Also Reference NicSearchResult Class NicSearchResult Overload Keyence.AutoID.SDK Namespace

#### NicSearchResult Properties

﻿ NicSearchResult Properties Keyence.AutoID.SDK Class Library NicSearchResult Properties The NicSearchResult type exposes the following members. Properties 
 Name Description NicBroadCastIpAddr 
 Broadcast IP address of Network Interface Card.
 NicIpAddr 
 IP address of Network Interface Card.
 NicIpv4Mask 
 IPv4 subnet mask of Network Interface Card.
 NicName 
 Name of Network Interface Card.
 Top See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

##### NicBroadCastIpAddr Property 

﻿ NicSearchResult.NicBroadCastIpAddr Property Keyence.AutoID.SDK Class Library NicSearchResult NicBroadCastIpAddr Property 
 Broadcast IP address of Network Interface Card.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string NicBroadCastIpAddr { get ; } Public ReadOnly Property NicBroadCastIpAddr As String 
 Get Property Value Type:  String See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

##### NicIpAddr Property 

﻿ NicSearchResult.NicIpAddr Property Keyence.AutoID.SDK Class Library NicSearchResult NicIpAddr Property 
 IP address of Network Interface Card.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string NicIpAddr { get ; } Public ReadOnly Property NicIpAddr As String 
 Get Property Value Type:  String See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

##### NicIpv4Mask Property 

﻿ NicSearchResult.NicIpv4Mask Property Keyence.AutoID.SDK Class Library NicSearchResult NicIpv4Mask Property 
 IPv4 subnet mask of Network Interface Card.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string NicIpv4Mask { get ; } Public ReadOnly Property NicIpv4Mask As String 
 Get Property Value Type:  String See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

##### NicName Property 

﻿ NicSearchResult.NicName Property Keyence.AutoID.SDK Class Library NicSearchResult NicName Property 
 Name of Network Interface Card.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string NicName { get ; } Public ReadOnly Property NicName As String 
 Get Property Value Type:  String See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

#### NicSearchResult Methods

﻿ NicSearchResult Methods Keyence.AutoID.SDK Class Library NicSearchResult Methods The NicSearchResult type exposes the following members. Methods 
 Name Description Equals (Inherited from Object .) Finalize (Inherited from Object .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) ToString (Inherited from Object .) Top See Also Reference NicSearchResult Class Keyence.AutoID.SDK Namespace

### ReaderAccessor Class

﻿ ReaderAccessor Class Keyence.AutoID.SDK Class Library ReaderAccessor Class 
 Reader Access Functions. (receive read data, execute command operation, handle reader's file)
 Inheritance Hierarchy System Object    Keyence.AutoID.SDK ReaderAccessor 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public class ReaderAccessor : IDisposable Public Class ReaderAccessor 
 Implements IDisposable The ReaderAccessor type exposes the following members. Constructors 
 Name Description ReaderAccessor 
 This class represents ReaderAccessor.
 ReaderAccessor(String) 
 This class represents ReaderAccessor with setting an IP address.
 Top Properties 
 Name Description CommandPort 
 CommandPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 DataPort 
 DataPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 IpAddress 
 IP address of SR. Default is "192.168.100.100". 
 This property is applied when calling “Connect” method.
 LastErrorInfo 
 Last error information of ReaderAccessor.
 Top Methods 
 Name Description CloseFtp 
 Close FTP connection.
 Connect 
 Connect a SR using TCP/IP. 
 Connect(Action Byte ) 
 Connect a SR using TCP/IP with setting received action. 
 DeleteFile 
 Deletion of file in SR.
 Disconnect 
 Disconnect TCP/IP.
 Dispose 
 Release the resources used by the ReaderAccessor.
 Equals (Inherited from Object .) ExecCommand(String) 
 Send a command. (Timeout is 1000ms.) 
 Only ASCII characters are supported.
 ExecCommand(String, Int32) 
 Send a command with setting a command timeout (0-65535ms). 0 is only for sending command. 
 Only ASCII characters are supported.
 Finalize (Inherited from Object .) GetFile 
 File receive form SR.
 GetFileList 
 Acquisition of file information list in SR.
 GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) OpenFtp 
 Open FTP connection.
 PutFile 
 File sending from PC to SR.
 ToString (Inherited from Object .) Top See Also Reference Keyence.AutoID.SDK Namespace

#### ReaderAccessor Constructor 

﻿ ReaderAccessor Constructor Keyence.AutoID.SDK Class Library ReaderAccessor Constructor Overload List 
 Name Description ReaderAccessor 
 This class represents ReaderAccessor.
 ReaderAccessor(String) 
 This class represents ReaderAccessor with setting an IP address.
 Top See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### ReaderAccessor Constructor 

﻿ ReaderAccessor Constructor Keyence.AutoID.SDK Class Library ReaderAccessor Constructor 
 This class represents ReaderAccessor.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ReaderAccessor () Public Sub New See Also Reference ReaderAccessor Class ReaderAccessor Overload Keyence.AutoID.SDK Namespace

##### ReaderAccessor Constructor (String)

﻿ ReaderAccessor Constructor (String) Keyence.AutoID.SDK Class Library ReaderAccessor Constructor (String) 
 This class represents ReaderAccessor with setting an IP address.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ReaderAccessor (
 string ipaddr 
) Public Sub New ( 
 ipaddr As String 
) Parameters ipaddr Type:  System String IP address of SR. See Also Reference ReaderAccessor Class ReaderAccessor Overload Keyence.AutoID.SDK Namespace

#### ReaderAccessor Properties

﻿ ReaderAccessor Properties Keyence.AutoID.SDK Class Library ReaderAccessor Properties The ReaderAccessor type exposes the following members. Properties 
 Name Description CommandPort 
 CommandPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 DataPort 
 DataPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 IpAddress 
 IP address of SR. Default is "192.168.100.100". 
 This property is applied when calling “Connect” method.
 LastErrorInfo 
 Last error information of ReaderAccessor.
 Top See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### CommandPort Property 

﻿ ReaderAccessor.CommandPort Property Keyence.AutoID.SDK Class Library ReaderAccessor CommandPort Property 
 CommandPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int CommandPort { get ; set ; } Public Property CommandPort As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### DataPort Property 

﻿ ReaderAccessor.DataPort Property Keyence.AutoID.SDK Class Library ReaderAccessor DataPort Property 
 DataPort (1-65535). Default is 9004. 
 This property is applied when calling “Connect” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int DataPort { get ; set ; } Public Property DataPort As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### IpAddress Property 

﻿ ReaderAccessor.IpAddress Property Keyence.AutoID.SDK Class Library ReaderAccessor IpAddress Property 
 IP address of SR. Default is "192.168.100.100". 
 This property is applied when calling “Connect” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string IpAddress { get ; set ; } Public Property IpAddress As String 
 Get 
 Set Property Value Type:  String See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### LastErrorInfo Property 

﻿ ReaderAccessor.LastErrorInfo Property Keyence.AutoID.SDK Class Library ReaderAccessor LastErrorInfo Property 
 Last error information of ReaderAccessor.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ErrorCode LastErrorInfo { get ; } Public ReadOnly Property LastErrorInfo As ErrorCode 
 Get Property Value Type:  ErrorCode See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

#### ReaderAccessor Methods

﻿ ReaderAccessor Methods Keyence.AutoID.SDK Class Library ReaderAccessor Methods The ReaderAccessor type exposes the following members. Methods 
 Name Description CloseFtp 
 Close FTP connection.
 Connect 
 Connect a SR using TCP/IP. 
 Connect(Action Byte ) 
 Connect a SR using TCP/IP with setting received action. 
 DeleteFile 
 Deletion of file in SR.
 Disconnect 
 Disconnect TCP/IP.
 Dispose 
 Release the resources used by the ReaderAccessor.
 Equals (Inherited from Object .) ExecCommand(String) 
 Send a command. (Timeout is 1000ms.) 
 Only ASCII characters are supported.
 ExecCommand(String, Int32) 
 Send a command with setting a command timeout (0-65535ms). 0 is only for sending command. 
 Only ASCII characters are supported.
 Finalize (Inherited from Object .) GetFile 
 File receive form SR.
 GetFileList 
 Acquisition of file information list in SR.
 GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) OpenFtp 
 Open FTP connection.
 PutFile 
 File sending from PC to SR.
 ToString (Inherited from Object .) Top See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### CloseFtp Method 

﻿ ReaderAccessor.CloseFtp Method Keyence.AutoID.SDK Class Library ReaderAccessor CloseFtp Method 
 Close FTP connection.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void CloseFtp () Public Sub CloseFtp See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### Connect Method 

﻿ ReaderAccessor.Connect Method Keyence.AutoID.SDK Class Library ReaderAccessor Connect Method Overload List 
 Name Description Connect 
 Connect a SR using TCP/IP. 
 Connect(Action Byte ) 
 Connect a SR using TCP/IP with setting received action. 
 Top See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

###### Connect Method 

﻿ ReaderAccessor.Connect Method Keyence.AutoID.SDK Class Library ReaderAccessor Connect Method 
 Connect a SR using TCP/IP. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool Connect () Public Function Connect As Boolean Return Value Type:  Boolean return true when connect TCP/IP successfully. See Also Reference ReaderAccessor Class Connect Overload Keyence.AutoID.SDK Namespace

###### Connect Method (Action(Byte[]))

﻿ ReaderAccessor.Connect Method (Action(Byte[])) Keyence.AutoID.SDK Class Library ReaderAccessor Connect Method (Action Byte ) 
 Connect a SR using TCP/IP with setting received action. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool Connect (
 Action < byte []> notify 
) Public Function Connect ( 
 notify As Action ( Of Byte ())
) As Boolean Parameters notify Type:  System Action Byte callback when data received. Return Value Type:  Boolean return true when connect TCP/IP successfully. See Also Reference ReaderAccessor Class Connect Overload Keyence.AutoID.SDK Namespace

##### DeleteFile Method 

﻿ ReaderAccessor.DeleteFile Method Keyence.AutoID.SDK Class Library ReaderAccessor DeleteFile Method 
 Deletion of file in SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool DeleteFile (
 string file 
) Public Function DeleteFile ( 
 file As String 
) As Boolean Parameters file Type:  System String File name to be deleted.(e.g. file="CONFIG\CONFIG1.PTC") Return Value Type:  Boolean return true when delete a file successfully. See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### Disconnect Method 

﻿ ReaderAccessor.Disconnect Method Keyence.AutoID.SDK Class Library ReaderAccessor Disconnect Method 
 Disconnect TCP/IP.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void Disconnect () Public Sub Disconnect See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### Dispose Method 

﻿ ReaderAccessor.Dispose Method Keyence.AutoID.SDK Class Library ReaderAccessor Dispose Method 
 Release the resources used by the ReaderAccessor.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void Dispose () Public Sub Dispose Implements IDisposable Dispose See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### ExecCommand Method 

﻿ ReaderAccessor.ExecCommand Method Keyence.AutoID.SDK Class Library ReaderAccessor ExecCommand Method Overload List 
 Name Description ExecCommand(String) 
 Send a command. (Timeout is 1000ms.) 
 Only ASCII characters are supported.
 ExecCommand(String, Int32) 
 Send a command with setting a command timeout (0-65535ms). 0 is only for sending command. 
 Only ASCII characters are supported.
 Top See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

###### ExecCommand Method (String)

﻿ ReaderAccessor.ExecCommand Method (String) Keyence.AutoID.SDK Class Library ReaderAccessor ExecCommand Method (String) 
 Send a command. (Timeout is 1000ms.) 
 Only ASCII characters are supported.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string ExecCommand (
 string command 
) Public Function ExecCommand ( 
 command As String 
) As String Parameters command Type:  System String Command for send Return Value Type:  String return command response. See Also Reference ReaderAccessor Class ExecCommand Overload Keyence.AutoID.SDK Namespace

###### ExecCommand Method (String, Int32)

﻿ ReaderAccessor.ExecCommand Method (String, Int32) Keyence.AutoID.SDK Class Library ReaderAccessor ExecCommand Method (String, Int32) 
 Send a command with setting a command timeout (0-65535ms). 0 is only for sending command. 
 Only ASCII characters are supported.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string ExecCommand (
 string command ,
 int timeoutms 
) Public Function ExecCommand ( 
 command As String ,
 timeoutms As Integer 
) As String Parameters command Type:  System String Command for send timeoutms Type:  System Int32 Command timeout Return Value Type:  String return command response. See Also Reference ReaderAccessor Class ExecCommand Overload Keyence.AutoID.SDK Namespace

##### GetFile Method 

﻿ ReaderAccessor.GetFile Method Keyence.AutoID.SDK Class Library ReaderAccessor GetFile Method 
 File receive form SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool GetFile (
 string srcFile ,
 string dstFile 
) Public Function GetFile ( 
 srcFile As String ,
 dstFile As String 
) As Boolean Parameters srcFile Type:  System String File name of the transfer source (SR side)(e.g. "CONFIG\CONFIG1.PTC") dstFile Type:  System String File name of the destination (PC side) Return Value Type:  Boolean return true when get a file successfully. See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### GetFileList Method 

﻿ ReaderAccessor.GetFileList Method Keyence.AutoID.SDK Class Library ReaderAccessor GetFileList Method 
 Acquisition of file information list in SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public List < string > GetFileList (
 string path 
) Public Function GetFileList ( 
 path As String 
) As List ( Of String ) Parameters path Type:  System String Folder name to get a list. (e.g. "IMAGE") Return Value Type:  List String List of file name See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### OpenFtp Method 

﻿ ReaderAccessor.OpenFtp Method Keyence.AutoID.SDK Class Library ReaderAccessor OpenFtp Method 
 Open FTP connection.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool OpenFtp () Public Function OpenFtp As Boolean Return Value Type:  Boolean return true when connect FTP successfully. See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

##### PutFile Method 

﻿ ReaderAccessor.PutFile Method Keyence.AutoID.SDK Class Library ReaderAccessor PutFile Method 
 File sending from PC to SR.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool PutFile (
 string srcFile ,
 string dstFile 
) Public Function PutFile ( 
 srcFile As String ,
 dstFile As String 
) As Boolean Parameters srcFile Type:  System String File name of the transfer source (PC side) dstFile Type:  System String File name of the destination (SR side) (e.g. "CONFIG\CONFIG1.PTC") Return Value Type:  Boolean return true when put a file successfully. See Also Reference ReaderAccessor Class Keyence.AutoID.SDK Namespace

### ReaderSearcher Class

﻿ ReaderSearcher Class Keyence.AutoID.SDK Class Library ReaderSearcher Class 
 SR Search Functions. (search SR in current networks, get SR information)
 Inheritance Hierarchy System Object    Keyence.AutoID.SDK ReaderSearcher 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public class ReaderSearcher : IDisposable Public Class ReaderSearcher 
 Implements IDisposable The ReaderSearcher type exposes the following members. Constructors 
 Name Description ReaderSearcher 
 This class represents ReaderSearcher.
 Top Properties 
 Name Description IsSearching 
 Operating state of SR searching process.
 SelectedNicSearchResult 
 Network Interface Card for SR searching process. This property is applied when calling “Start” method.
 TimeoutMs 
 Timeout of SR searching process (1-65535ms). Default is 5000ms. 
 This property is applied when calling “Start” method.
 Top Methods 
 Name Description Dispose 
 Release the resources used by the ReaderSearcher. 
 Equals (Inherited from Object .) Finalize 
 Destructor.
 (Overrides Object Finalize .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) ListUpNic 
 List up Network Interface Card.
 MemberwiseClone (Inherited from Object .) Start 
 Start SR searching process. Search until timeout expired. 
 Stop 
 Stop SR searching process.
 ToString (Inherited from Object .) Top See Also Reference Keyence.AutoID.SDK Namespace

#### ReaderSearcher Constructor 

﻿ ReaderSearcher Constructor Keyence.AutoID.SDK Class Library ReaderSearcher Constructor 
 This class represents ReaderSearcher.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ReaderSearcher () Public Sub New See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

#### ReaderSearcher Properties

﻿ ReaderSearcher Properties Keyence.AutoID.SDK Class Library ReaderSearcher Properties The ReaderSearcher type exposes the following members. Properties 
 Name Description IsSearching 
 Operating state of SR searching process.
 SelectedNicSearchResult 
 Network Interface Card for SR searching process. This property is applied when calling “Start” method.
 TimeoutMs 
 Timeout of SR searching process (1-65535ms). Default is 5000ms. 
 This property is applied when calling “Start” method.
 Top See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### IsSearching Property 

﻿ ReaderSearcher.IsSearching Property Keyence.AutoID.SDK Class Library ReaderSearcher IsSearching Property 
 Operating state of SR searching process.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool IsSearching { get ; } Public ReadOnly Property IsSearching As Boolean 
 Get Property Value Type:  Boolean See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### SelectedNicSearchResult Property 

﻿ ReaderSearcher.SelectedNicSearchResult Property Keyence.AutoID.SDK Class Library ReaderSearcher SelectedNicSearchResult Property 
 Network Interface Card for SR searching process. This property is applied when calling “Start” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public NicSearchResult SelectedNicSearchResult { get ; set ; } Public Property SelectedNicSearchResult As NicSearchResult 
 Get 
 Set Property Value Type:  NicSearchResult See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### TimeoutMs Property 

﻿ ReaderSearcher.TimeoutMs Property Keyence.AutoID.SDK Class Library ReaderSearcher TimeoutMs Property 
 Timeout of SR searching process (1-65535ms). Default is 5000ms. 
 This property is applied when calling “Start” method.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public int TimeoutMs { get ; set ; } Public Property TimeoutMs As Integer 
 Get 
 Set Property Value Type:  Int32 See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

#### ReaderSearcher Methods

﻿ ReaderSearcher Methods Keyence.AutoID.SDK Class Library ReaderSearcher Methods The ReaderSearcher type exposes the following members. Methods 
 Name Description Dispose 
 Release the resources used by the ReaderSearcher. 
 Equals (Inherited from Object .) Finalize 
 Destructor.
 (Overrides Object Finalize .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) ListUpNic 
 List up Network Interface Card.
 MemberwiseClone (Inherited from Object .) Start 
 Start SR searching process. Search until timeout expired. 
 Stop 
 Stop SR searching process.
 ToString (Inherited from Object .) Top See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### Dispose Method 

﻿ ReaderSearcher.Dispose Method Keyence.AutoID.SDK Class Library ReaderSearcher Dispose Method 
 Release the resources used by the ReaderSearcher. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void Dispose () Public Sub Dispose Implements IDisposable Dispose See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### Finalize Method 

﻿ ReaderSearcher.Finalize Method Keyence.AutoID.SDK Class Library ReaderSearcher Finalize Method 
 Destructor.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy protected override void Finalize () Protected Overrides Sub Finalize Implements Object Finalize See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### ListUpNic Method 

﻿ ReaderSearcher.ListUpNic Method Keyence.AutoID.SDK Class Library ReaderSearcher ListUpNic Method 
 List up Network Interface Card.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public List < NicSearchResult > ListUpNic () Public Function ListUpNic As List ( Of NicSearchResult ) Return Value Type:  List NicSearchResult List of NicSearchResult. See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### Start Method 

﻿ ReaderSearcher.Start Method Keyence.AutoID.SDK Class Library ReaderSearcher Start Method 
 Start SR searching process. Search until timeout expired. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public bool Start (
 Action < ReaderSearchResult > resultNotify 
) Public Function Start ( 
 resultNotify As Action ( Of ReaderSearchResult )
) As Boolean Parameters resultNotify Type:  System Action ReaderSearchResult callback when SR found, and timeout reached. Return Value Type:  Boolean return true when searching reader was started. See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

##### Stop Method 

﻿ ReaderSearcher.Stop Method Keyence.AutoID.SDK Class Library ReaderSearcher Stop Method 
 Stop SR searching process.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public void Stop () Public Sub Stop See Also Reference ReaderSearcher Class Keyence.AutoID.SDK Namespace

### ReaderSearchResult Class

﻿ ReaderSearchResult Class Keyence.AutoID.SDK Class Library ReaderSearchResult Class 
 A result of ReaderSearcher.Start Method.
 Inheritance Hierarchy System Object    Keyence.AutoID.SDK ReaderSearchResult 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public class ReaderSearchResult Public Class ReaderSearchResult The ReaderSearchResult type exposes the following members. Constructors 
 Name Description ReaderSearchResult 
 This class represents ReaderSearchResult. 
 ReaderSearchResult(String, String, String) 
 This class represents ReaderSearchResult. 
 Top Properties 
 Name Description IpAddress 
 SR's IP Address .
 ReaderModel 
 SR's Model Type.
 ReaderName 
 SR's Setting Name.
 Top Methods 
 Name Description Equals (Inherited from Object .) Finalize (Inherited from Object .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) ToString (Inherited from Object .) Top See Also Reference Keyence.AutoID.SDK Namespace

#### ReaderSearchResult Constructor 

﻿ ReaderSearchResult Constructor Keyence.AutoID.SDK Class Library ReaderSearchResult Constructor Overload List 
 Name Description ReaderSearchResult 
 This class represents ReaderSearchResult. 
 ReaderSearchResult(String, String, String) 
 This class represents ReaderSearchResult. 
 Top See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

##### ReaderSearchResult Constructor 

﻿ ReaderSearchResult Constructor Keyence.AutoID.SDK Class Library ReaderSearchResult Constructor 
 This class represents ReaderSearchResult. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ReaderSearchResult () Public Sub New See Also Reference ReaderSearchResult Class ReaderSearchResult Overload Keyence.AutoID.SDK Namespace

##### ReaderSearchResult Constructor (String, String, String)

﻿ ReaderSearchResult Constructor (String, String, String) Keyence.AutoID.SDK Class Library ReaderSearchResult Constructor (String, String, String) 
 This class represents ReaderSearchResult. 
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public ReaderSearchResult (
 string model ,
 string name ,
 string ipAddr 
) Public Sub New ( 
 model As String ,
 name As String ,
 ipAddr As String 
) Parameters model Type:  System String Reader's Model Type. name Type:  System String Reader's Setting Name. ipAddr Type:  System String Reader'sIP Address. See Also Reference ReaderSearchResult Class ReaderSearchResult Overload Keyence.AutoID.SDK Namespace

#### ReaderSearchResult Properties

﻿ ReaderSearchResult Properties Keyence.AutoID.SDK Class Library ReaderSearchResult Properties The ReaderSearchResult type exposes the following members. Properties 
 Name Description IpAddress 
 SR's IP Address .
 ReaderModel 
 SR's Model Type.
 ReaderName 
 SR's Setting Name.
 Top See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

##### IpAddress Property 

﻿ ReaderSearchResult.IpAddress Property Keyence.AutoID.SDK Class Library ReaderSearchResult IpAddress Property 
 SR's IP Address .
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string IpAddress { get ; } Public ReadOnly Property IpAddress As String 
 Get Property Value Type:  String See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

##### ReaderModel Property 

﻿ ReaderSearchResult.ReaderModel Property Keyence.AutoID.SDK Class Library ReaderSearchResult ReaderModel Property 
 SR's Model Type.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string ReaderModel { get ; } Public ReadOnly Property ReaderModel As String 
 Get Property Value Type:  String See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

##### ReaderName Property 

﻿ ReaderSearchResult.ReaderName Property Keyence.AutoID.SDK Class Library ReaderSearchResult ReaderName Property 
 SR's Setting Name.
 Namespace: 
   Keyence.AutoID.SDK 
 Assembly: 
  Keyence.AutoID.SDK (in Keyence.AutoID.SDK.dll) Version: 2.0.0.0 (2.0.0.0) Syntax C# VB Copy public string ReaderName { get ; } Public ReadOnly Property ReaderName As String 
 Get Property Value Type:  String See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

#### ReaderSearchResult Methods

﻿ ReaderSearchResult Methods Keyence.AutoID.SDK Class Library ReaderSearchResult Methods The ReaderSearchResult type exposes the following members. Methods 
 Name Description Equals (Inherited from Object .) Finalize (Inherited from Object .) GetHashCode (Inherited from Object .) GetType (Inherited from Object .) MemberwiseClone (Inherited from Object .) ToString (Inherited from Object .) Top See Also Reference ReaderSearchResult Class Keyence.AutoID.SDK Namespace

