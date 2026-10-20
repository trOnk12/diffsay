plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("io.github.takahirom.roborazzi")
}
android {
    namespace = "dev.sample"
    compileSdk = 35
    defaultConfig { minSdk = 26; targetSdk = 35 }
    buildFeatures { compose = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    testOptions { unitTests { isIncludeAndroidResources = true } }
}
dependencies {
    val bom = platform("androidx.compose:compose-bom:2025.06.00")
    implementation(bom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.9.3")
    testImplementation(bom)
    testImplementation("androidx.compose.ui:ui-test-junit4")
    testImplementation("androidx.compose.ui:ui-tooling-data")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.32.2")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.32.2")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
tasks.withType<Test>().configureEach {
    systemProperty("mutation", (project.findProperty("mutation") ?: "none").toString())
    // Robolectric's native graphics
    systemProperty("robolectric.graphicsMode", "NATIVE")
    systemProperty("robolectric.dependency.repo.url", "https://maven-central.storage-download.googleapis.com/maven2")
    systemProperty("robolectric.dependency.repo.id", "gcs-central")
    jvmArgs("-Dhttps.proxyHost=127.0.0.1", "-Dhttps.proxyPort=41521")
}
composeCompiler { includeSourceInformation.set(true) }
