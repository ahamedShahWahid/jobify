import 'package:flutter/widgets.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

// Conditional import: the web impl pulls in `google_sign_in_web/web_only.dart`
// (dart:js_interop), which does NOT compile on mobile or in `flutter test`.
// The stub is selected everywhere except the web build.
import 'package:kpa_app/data/auth/google_web_sign_in_stub.dart'
    if (dart.library.js_interop) 'package:kpa_app/data/auth/google_web_sign_in_web.dart'
    as impl;

part 'google_web_sign_in.g.dart';

/// Web-only Google Sign-In.
///
/// On the web, Google Identity Services separates *authentication* (an ID
/// token, obtainable only via the Google-rendered button / One Tap) from
/// *authorization* (an access token, via the imperative `signIn()`). The
/// imperative path therefore can't yield an ID token — so the web flow is
/// event-driven: render [button], listen to [idTokens], hand the token to
/// `AuthRepositoryImpl.completeWebSignIn`.
///
/// On non-web platforms a no-op stub is selected; the imperative
/// `GoogleSignInDataSource.getIdToken()` is used instead.
abstract interface class GoogleWebSignIn {
  /// Force the GIS client to initialize so [button] can render. Must complete
  /// before [button] is built — `renderButton()` asserts init has run.
  Future<void> initialize();

  /// Emits an ID token each time the user completes the rendered-button flow.
  Stream<String> get idTokens;

  /// The Google-rendered sign-in button widget.
  Widget button();

  /// Cancel the subscription + close the stream.
  void dispose();
}

/// Initialized [GoogleWebSignIn]. Awaiting [initialize] inside the provider
/// guarantees the widget tree only reaches [GoogleWebSignIn.button] after the
/// GIS client is ready.
@Riverpod(keepAlive: true)
Future<GoogleWebSignIn> googleWebSignIn(Ref ref) async {
  final google = impl.createGoogleWebSignIn();
  ref.onDispose(google.dispose);
  await google.initialize();
  return google;
}
