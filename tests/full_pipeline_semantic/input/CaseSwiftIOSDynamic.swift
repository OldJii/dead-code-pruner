import UIKit

final class CaseSwiftIOSDynamic: UIViewController {
    private func storyboardOnly() {
    }

    private func selectorOnly() {
    }

    @IBAction func buttonTapped(_ sender: UIButton) {
    }

    private func removableHook() {
    }

    func wire() {
        _ = #selector(selectorOnly)
        removableHook()
    }
}
