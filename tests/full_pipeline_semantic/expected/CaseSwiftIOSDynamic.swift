import UIKit

final class CaseSwiftIOSDynamic: UIViewController {
    private func storyboardOnly() {
    }

    private func selectorOnly() {
    }

    @IBAction func buttonTapped(_ sender: UIButton) {
    }

    func wire() {
        _ = #selector(selectorOnly)
    }
}
