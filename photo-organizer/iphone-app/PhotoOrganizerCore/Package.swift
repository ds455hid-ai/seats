// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "PhotoOrganizerCore",
    platforms: [
        .iOS(.v15),
        .macOS(.v12),
    ],
    products: [
        .library(name: "PhotoOrganizerCore", targets: ["PhotoOrganizerCore"]),
    ],
    targets: [
        .target(name: "PhotoOrganizerCore"),
        .testTarget(name: "PhotoOrganizerCoreTests", dependencies: ["PhotoOrganizerCore"]),
    ]
)
