// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'me_dto.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$MeDto {
  MeUserDto get user;
  ApplicantSummaryDto? get applicant;

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $MeDtoCopyWith<MeDto> get copyWith =>
      _$MeDtoCopyWithImpl<MeDto>(this as MeDto, _$identity);

  /// Serializes this MeDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is MeDto &&
            (identical(other.user, user) || other.user == user) &&
            (identical(other.applicant, applicant) ||
                other.applicant == applicant));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, user, applicant);

  @override
  String toString() {
    return 'MeDto(user: $user, applicant: $applicant)';
  }
}

/// @nodoc
abstract mixin class $MeDtoCopyWith<$Res> {
  factory $MeDtoCopyWith(MeDto value, $Res Function(MeDto) _then) =
      _$MeDtoCopyWithImpl;
  @useResult
  $Res call({MeUserDto user, ApplicantSummaryDto? applicant});

  $MeUserDtoCopyWith<$Res> get user;
  $ApplicantSummaryDtoCopyWith<$Res>? get applicant;
}

/// @nodoc
class _$MeDtoCopyWithImpl<$Res> implements $MeDtoCopyWith<$Res> {
  _$MeDtoCopyWithImpl(this._self, this._then);

  final MeDto _self;
  final $Res Function(MeDto) _then;

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? user = null,
    Object? applicant = freezed,
  }) {
    return _then(_self.copyWith(
      user: null == user
          ? _self.user
          : user // ignore: cast_nullable_to_non_nullable
              as MeUserDto,
      applicant: freezed == applicant
          ? _self.applicant
          : applicant // ignore: cast_nullable_to_non_nullable
              as ApplicantSummaryDto?,
    ));
  }

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MeUserDtoCopyWith<$Res> get user {
    return $MeUserDtoCopyWith<$Res>(_self.user, (value) {
      return _then(_self.copyWith(user: value));
    });
  }

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicantSummaryDtoCopyWith<$Res>? get applicant {
    if (_self.applicant == null) {
      return null;
    }

    return $ApplicantSummaryDtoCopyWith<$Res>(_self.applicant!, (value) {
      return _then(_self.copyWith(applicant: value));
    });
  }
}

/// Adds pattern-matching-related methods to [MeDto].
extension MeDtoPatterns on MeDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_MeDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MeDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_MeDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_MeDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(MeUserDto user, ApplicantSummaryDto? applicant)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MeDto() when $default != null:
        return $default(_that.user, _that.applicant);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(MeUserDto user, ApplicantSummaryDto? applicant) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeDto():
        return $default(_that.user, _that.applicant);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(MeUserDto user, ApplicantSummaryDto? applicant)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeDto() when $default != null:
        return $default(_that.user, _that.applicant);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _MeDto implements MeDto {
  const _MeDto({required this.user, this.applicant});
  factory _MeDto.fromJson(Map<String, dynamic> json) => _$MeDtoFromJson(json);

  @override
  final MeUserDto user;
  @override
  final ApplicantSummaryDto? applicant;

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$MeDtoCopyWith<_MeDto> get copyWith =>
      __$MeDtoCopyWithImpl<_MeDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$MeDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _MeDto &&
            (identical(other.user, user) || other.user == user) &&
            (identical(other.applicant, applicant) ||
                other.applicant == applicant));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, user, applicant);

  @override
  String toString() {
    return 'MeDto(user: $user, applicant: $applicant)';
  }
}

/// @nodoc
abstract mixin class _$MeDtoCopyWith<$Res> implements $MeDtoCopyWith<$Res> {
  factory _$MeDtoCopyWith(_MeDto value, $Res Function(_MeDto) _then) =
      __$MeDtoCopyWithImpl;
  @override
  @useResult
  $Res call({MeUserDto user, ApplicantSummaryDto? applicant});

  @override
  $MeUserDtoCopyWith<$Res> get user;
  @override
  $ApplicantSummaryDtoCopyWith<$Res>? get applicant;
}

/// @nodoc
class __$MeDtoCopyWithImpl<$Res> implements _$MeDtoCopyWith<$Res> {
  __$MeDtoCopyWithImpl(this._self, this._then);

  final _MeDto _self;
  final $Res Function(_MeDto) _then;

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? user = null,
    Object? applicant = freezed,
  }) {
    return _then(_MeDto(
      user: null == user
          ? _self.user
          : user // ignore: cast_nullable_to_non_nullable
              as MeUserDto,
      applicant: freezed == applicant
          ? _self.applicant
          : applicant // ignore: cast_nullable_to_non_nullable
              as ApplicantSummaryDto?,
    ));
  }

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MeUserDtoCopyWith<$Res> get user {
    return $MeUserDtoCopyWith<$Res>(_self.user, (value) {
      return _then(_self.copyWith(user: value));
    });
  }

  /// Create a copy of MeDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicantSummaryDtoCopyWith<$Res>? get applicant {
    if (_self.applicant == null) {
      return null;
    }

    return $ApplicantSummaryDtoCopyWith<$Res>(_self.applicant!, (value) {
      return _then(_self.copyWith(applicant: value));
    });
  }
}

/// @nodoc
mixin _$MeUserDto {
  String get id;
  String get email;
  String get role;
  DateTime get createdAt;
  String? get displayName;

  /// Create a copy of MeUserDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $MeUserDtoCopyWith<MeUserDto> get copyWith =>
      _$MeUserDtoCopyWithImpl<MeUserDto>(this as MeUserDto, _$identity);

  /// Serializes this MeUserDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is MeUserDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.email, email) || other.email == email) &&
            (identical(other.role, role) || other.role == role) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt) &&
            (identical(other.displayName, displayName) ||
                other.displayName == displayName));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, id, email, role, createdAt, displayName);

  @override
  String toString() {
    return 'MeUserDto(id: $id, email: $email, role: $role, createdAt: $createdAt, displayName: $displayName)';
  }
}

/// @nodoc
abstract mixin class $MeUserDtoCopyWith<$Res> {
  factory $MeUserDtoCopyWith(MeUserDto value, $Res Function(MeUserDto) _then) =
      _$MeUserDtoCopyWithImpl;
  @useResult
  $Res call(
      {String id,
      String email,
      String role,
      DateTime createdAt,
      String? displayName});
}

/// @nodoc
class _$MeUserDtoCopyWithImpl<$Res> implements $MeUserDtoCopyWith<$Res> {
  _$MeUserDtoCopyWithImpl(this._self, this._then);

  final MeUserDto _self;
  final $Res Function(MeUserDto) _then;

  /// Create a copy of MeUserDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? email = null,
    Object? role = null,
    Object? createdAt = null,
    Object? displayName = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      email: null == email
          ? _self.email
          : email // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _self.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      displayName: freezed == displayName
          ? _self.displayName
          : displayName // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [MeUserDto].
extension MeUserDtoPatterns on MeUserDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_MeUserDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MeUserDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_MeUserDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeUserDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_MeUserDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeUserDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String id, String email, String role, DateTime createdAt,
            String? displayName)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MeUserDto() when $default != null:
        return $default(_that.id, _that.email, _that.role, _that.createdAt,
            _that.displayName);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String id, String email, String role, DateTime createdAt,
            String? displayName)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeUserDto():
        return $default(_that.id, _that.email, _that.role, _that.createdAt,
            _that.displayName);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(String id, String email, String role, DateTime createdAt,
            String? displayName)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MeUserDto() when $default != null:
        return $default(_that.id, _that.email, _that.role, _that.createdAt,
            _that.displayName);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _MeUserDto implements MeUserDto {
  const _MeUserDto(
      {required this.id,
      required this.email,
      required this.role,
      required this.createdAt,
      this.displayName});
  factory _MeUserDto.fromJson(Map<String, dynamic> json) =>
      _$MeUserDtoFromJson(json);

  @override
  final String id;
  @override
  final String email;
  @override
  final String role;
  @override
  final DateTime createdAt;
  @override
  final String? displayName;

  /// Create a copy of MeUserDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$MeUserDtoCopyWith<_MeUserDto> get copyWith =>
      __$MeUserDtoCopyWithImpl<_MeUserDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$MeUserDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _MeUserDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.email, email) || other.email == email) &&
            (identical(other.role, role) || other.role == role) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt) &&
            (identical(other.displayName, displayName) ||
                other.displayName == displayName));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, id, email, role, createdAt, displayName);

  @override
  String toString() {
    return 'MeUserDto(id: $id, email: $email, role: $role, createdAt: $createdAt, displayName: $displayName)';
  }
}

/// @nodoc
abstract mixin class _$MeUserDtoCopyWith<$Res>
    implements $MeUserDtoCopyWith<$Res> {
  factory _$MeUserDtoCopyWith(
          _MeUserDto value, $Res Function(_MeUserDto) _then) =
      __$MeUserDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String id,
      String email,
      String role,
      DateTime createdAt,
      String? displayName});
}

/// @nodoc
class __$MeUserDtoCopyWithImpl<$Res> implements _$MeUserDtoCopyWith<$Res> {
  __$MeUserDtoCopyWithImpl(this._self, this._then);

  final _MeUserDto _self;
  final $Res Function(_MeUserDto) _then;

  /// Create a copy of MeUserDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? email = null,
    Object? role = null,
    Object? createdAt = null,
    Object? displayName = freezed,
  }) {
    return _then(_MeUserDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      email: null == email
          ? _self.email
          : email // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _self.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      displayName: freezed == displayName
          ? _self.displayName
          : displayName // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$ApplicantSummaryDto {
  String get id;
  String get userId;

  /// Create a copy of ApplicantSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $ApplicantSummaryDtoCopyWith<ApplicantSummaryDto> get copyWith =>
      _$ApplicantSummaryDtoCopyWithImpl<ApplicantSummaryDto>(
          this as ApplicantSummaryDto, _$identity);

  /// Serializes this ApplicantSummaryDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is ApplicantSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.userId, userId) || other.userId == userId));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, userId);

  @override
  String toString() {
    return 'ApplicantSummaryDto(id: $id, userId: $userId)';
  }
}

/// @nodoc
abstract mixin class $ApplicantSummaryDtoCopyWith<$Res> {
  factory $ApplicantSummaryDtoCopyWith(
          ApplicantSummaryDto value, $Res Function(ApplicantSummaryDto) _then) =
      _$ApplicantSummaryDtoCopyWithImpl;
  @useResult
  $Res call({String id, String userId});
}

/// @nodoc
class _$ApplicantSummaryDtoCopyWithImpl<$Res>
    implements $ApplicantSummaryDtoCopyWith<$Res> {
  _$ApplicantSummaryDtoCopyWithImpl(this._self, this._then);

  final ApplicantSummaryDto _self;
  final $Res Function(ApplicantSummaryDto) _then;

  /// Create a copy of ApplicantSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? userId = null,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      userId: null == userId
          ? _self.userId
          : userId // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// Adds pattern-matching-related methods to [ApplicantSummaryDto].
extension ApplicantSummaryDtoPatterns on ApplicantSummaryDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_ApplicantSummaryDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_ApplicantSummaryDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_ApplicantSummaryDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String id, String userId)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto() when $default != null:
        return $default(_that.id, _that.userId);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String id, String userId) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto():
        return $default(_that.id, _that.userId);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(String id, String userId)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicantSummaryDto() when $default != null:
        return $default(_that.id, _that.userId);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _ApplicantSummaryDto implements ApplicantSummaryDto {
  const _ApplicantSummaryDto({required this.id, required this.userId});
  factory _ApplicantSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantSummaryDtoFromJson(json);

  @override
  final String id;
  @override
  final String userId;

  /// Create a copy of ApplicantSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$ApplicantSummaryDtoCopyWith<_ApplicantSummaryDto> get copyWith =>
      __$ApplicantSummaryDtoCopyWithImpl<_ApplicantSummaryDto>(
          this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$ApplicantSummaryDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _ApplicantSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.userId, userId) || other.userId == userId));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, userId);

  @override
  String toString() {
    return 'ApplicantSummaryDto(id: $id, userId: $userId)';
  }
}

/// @nodoc
abstract mixin class _$ApplicantSummaryDtoCopyWith<$Res>
    implements $ApplicantSummaryDtoCopyWith<$Res> {
  factory _$ApplicantSummaryDtoCopyWith(_ApplicantSummaryDto value,
          $Res Function(_ApplicantSummaryDto) _then) =
      __$ApplicantSummaryDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String id, String userId});
}

/// @nodoc
class __$ApplicantSummaryDtoCopyWithImpl<$Res>
    implements _$ApplicantSummaryDtoCopyWith<$Res> {
  __$ApplicantSummaryDtoCopyWithImpl(this._self, this._then);

  final _ApplicantSummaryDto _self;
  final $Res Function(_ApplicantSummaryDto) _then;

  /// Create a copy of ApplicantSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? userId = null,
  }) {
    return _then(_ApplicantSummaryDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      userId: null == userId
          ? _self.userId
          : userId // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

// dart format on
