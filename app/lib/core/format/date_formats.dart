import 'package:intl/intl.dart';

/// Module-static formatters shared across screens; constructing DateFormat in
/// build methods repeats locale initialization work on every rebuild.
final jobifyShortDateFormat = DateFormat.yMMMd();
final jobifyLongDateFormat = DateFormat.yMMMMd();
