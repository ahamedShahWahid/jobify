import 'dart:typed_data';

// Conditional import: the web impl uses a Blob + anchor click via
// dart:js_interop + package:web, which do NOT compile on mobile or in
// `flutter test`. The stub is selected everywhere except the web build.
import 'package:jobify_app/presentation/recruiter/resume_saver/resume_saver_stub.dart'
    if (dart.library.js_interop) 'package:jobify_app/presentation/recruiter/resume_saver/resume_saver_web.dart'
    as impl;

/// Trigger a browser download (web) or show a "not available" message (mobile).
///
/// On web: creates a Blob URL, synthesises an anchor click, then revokes it.
/// On mobile: this function is a no-op stub — callers should show a SnackBar
/// explaining the limitation.
void saveResume(Uint8List bytes, String filename, String contentType) =>
    impl.saveResume(bytes, filename, contentType);
