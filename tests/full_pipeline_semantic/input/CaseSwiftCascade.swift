final class CaseSwiftCascade {
    private func disabled() -> Bool { return false }
    private static func enabled() -> Bool { return true }

    func render() {
        if disabled() {
            dead()
        }
        after()
    }

    func renderStatic() {
        if CaseSwiftCascade.enabled() {
            live()
        }
    }
}
