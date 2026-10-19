plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("io.sentry.android.gradle") version "5.0.0"
}

android {
    namespace = "com.example"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.example"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }
}

sentry {
    autoUploadProguardMapping.set(true)
}

dependencies {
    implementation("io.sentry:sentry-android:8.20.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
