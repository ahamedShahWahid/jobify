/// Tracks when the applicant last opened Feed, so the home summary can show
/// "N new matches since your last visit." Returns `null` from
/// [getLastSeenAt] on first-ever call (no stored baseline) — callers must
/// treat that as "0 new," never as "everything is new."
abstract class FeedVisitRepository {
  Future<DateTime?> getLastSeenAt();
  Future<void> setLastSeenAt(DateTime at);
}
