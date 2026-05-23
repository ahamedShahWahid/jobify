/// In-memory mutable holder for the current access token.
///
/// Lives below Riverpod's reach because dio interceptors are constructed
/// once and shouldn't take a Ref. The auth repository writes to this when
/// it mints/refreshes a token.
class AccessTokenHolder {
  String? _token;

  String? get current => _token;

  // ignore: use_setters_to_change_properties
  void set(String? token) {
    _token = token;
  }

  void clear() => set(null);
}
