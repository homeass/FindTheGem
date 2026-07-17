# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# Keep WebView related classes
-keepclassmembers class * extends android.webkit.WebViewClient {
    public *;
}

-keepclassmembers class * extends android.webkit.WebChromeClient {
    public *;
}

# Keep JavaScript interface classes
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Keep settings activity
-keep class com.findthegem.app.SettingsActivity { *; }
-keep class com.findthegem.app.MainActivity { *; }
-keep class com.findthegem.app.SplashActivity { *; }
-keep class com.findthegem.app.FindTheGemApplication { *; }

# Keep R classes
-keepclassmembers class **.R$* {
    public static <fields>;
}

# Keep view binding classes
-keep class com.findthegem.app.databinding.** { *; }

# Keep SwipeRefreshLayout
-keep class androidx.swiperefreshlayout.widget.SwipeRefreshLayout { *; }

# Keep Material Components
-keep class com.google.android.material.** { *; }

# Keep WebView
-keep class android.webkit.** { *; }
-keep class androidx.webkit.** { *; }

# Keep SharedPreferences
-keep class android.preference.PreferenceManager { *; }
-keep class android.content.SharedPreferences { *; }

# Keep network security config
-keep class android.security.NetworkSecurityPolicy { *; }
