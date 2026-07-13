package demo

const FEATURE_FLAG = true // placeholder overwritten by pruner pattern

func LiveExported() {
	println("live")
}

func Multiline(flag bool) {
	isOneWay :=
		false
	use(isOneWay)
}

func use(b bool) { println(b) }
